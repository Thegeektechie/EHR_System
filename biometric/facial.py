import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List, Generator
import json
from utils.helpers import BIOMETRIC_DIR, LABEL_MAP_FILE

# -----------------------------------------------------------
# Face Detection Configuration
# -----------------------------------------------------------
FACE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
FACE_CASCADE = cv2.CascadeClassifier(FACE_CASCADE_PATH)

FACE_SIZE = (200, 200)


def _detect_face_gray(gray_img: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Detect the largest face in a grayscale image.
    Returns bounding box or None.
    """
    faces = FACE_CASCADE.detectMultiScale(
        gray_img,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(80, 80)
    )

    if len(faces) == 0:
        return None

    faces = sorted(faces, key=lambda r: r[2] * r[3], reverse=True)
    return faces[0]


# -----------------------------------------------------------
# Automatic Face Capture (Used by Registration Progress Bar)
# -----------------------------------------------------------
def open_camera_and_capture(user_id: str, required_samples: int) -> Generator[int, None, None]:
    """
    Generator that automatically captures faces and yields progress events.
    """
    user_faces_dir = BIOMETRIC_DIR / user_id / "faces"
    user_faces_dir.mkdir(parents=True, exist_ok=True)

    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        raise RuntimeError("Camera could not be opened.")

    saved_count = 0

    while saved_count < required_samples:
        ret, frame = cam.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        face_rect = _detect_face_gray(gray)

        if face_rect is not None:
            x, y, w, h = face_rect
            face = gray[y:y + h, x:x + w]

            try:
                face_resized = cv2.resize(face, FACE_SIZE)
            except Exception:
                continue

            filepath = user_faces_dir / f"face_{saved_count + 1}.png"
            cv2.imwrite(str(filepath), face_resized)

            saved_count += 1
            yield 1

        cv2.waitKey(30)

    cam.release()
    cv2.destroyAllWindows()


# -----------------------------------------------------------
# Backward Compatibility Function
# -----------------------------------------------------------
def capture_and_save_face_samples(user_id: str, samples: int = 5):
    """
    Wraps the automatic capture system so older code calling this still works.
    """
    saved_paths = []
    saved_count = 0

    gen = open_camera_and_capture(user_id, samples)
    user_faces_dir = BIOMETRIC_DIR / user_id / "faces"

    for _ in gen:
        saved_count += 1
        saved_paths.append(str(user_faces_dir / f"face_{saved_count}.png"))

    return saved_count, saved_paths


# -----------------------------------------------------------
# Training Data Loader
# -----------------------------------------------------------
def _gather_training_data() -> Tuple[List[np.ndarray], List[int], dict]:
    faces = []
    labels = []
    label_map = {}
    current_label = 0

    for user_folder in sorted(BIOMETRIC_DIR.iterdir()):
        if not user_folder.is_dir():
            continue

        faces_dir = user_folder / "faces"
        if not faces_dir.exists():
            continue

        user_id = user_folder.name
        label_map[current_label] = user_id

        for img_path in faces_dir.glob("*.png"):
            img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue

            img_resized = cv2.resize(img, FACE_SIZE)
            faces.append(img_resized)
            labels.append(current_label)

        current_label += 1

    return faces, labels, label_map


# -----------------------------------------------------------
# Model Training
# -----------------------------------------------------------
def train_lbph_recognizer(model_path: Path = BIOMETRIC_DIR / "lbph_model.yml"):
    """
    Train LBPH model using all stored user images.
    """
    faces, labels, label_map = _gather_training_data()

    if len(faces) == 0:
        print("No training data available.")
        return False

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces, np.array(labels, dtype=np.int32))
    recognizer.write(str(model_path))

    with open(LABEL_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(label_map, f, indent=2)

    print(f"Model trained for {len(set(labels))} user(s).")
    return True


# -----------------------------------------------------------
# Face Prediction
# -----------------------------------------------------------
def predict_face(threshold: float = 60.0) -> Tuple[Optional[str], float]:
    """
    Capture a frame, detect face, and predict user identity.
    Returns (user_id, confidence).
    """
    model_path = BIOMETRIC_DIR / "lbph_model.yml"

    if not model_path.exists():
        print("No trained LBPH model found.")
        return None, float("inf")

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(str(model_path))

    with open(LABEL_MAP_FILE, "r", encoding="utf-8") as f:
        label_map = json.load(f)

    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        return None, float("inf")

    ret, frame = cam.read()
    cam.release()

    if not ret:
        return None, float("inf")

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    face_rect = _detect_face_gray(gray)

    if face_rect is None:
        return None, float("inf")

    x, y, w, h = face_rect
    face = gray[y:y + h, x:x + w]
    face_resized = cv2.resize(face, FACE_SIZE)

    label, confidence = recognizer.predict(face_resized)
    user_id = label_map.get(str(label)) or label_map.get(label)

    if user_id is None or confidence > threshold:
        return None, confidence

    return user_id, confidence
