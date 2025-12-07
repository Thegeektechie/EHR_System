import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List, Generator
import json
from utils.helpers import BIOMETRIC_DIR, LABEL_MAP_FILE

FACE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
FACE_CASCADE = cv2.CascadeClassifier(FACE_CASCADE_PATH)

FACE_SIZE = (200, 200)


def _detect_face_gray(gray_img: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
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


def open_camera_and_capture(user_id: str, required_samples: int) -> Generator[int, None, None]:
    """
    Automatically capture facial samples without requiring user input.
    Yields 1 each time a sample is saved. Used by progress bar thread.
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
            face = gray[y:y+h, x:x+w]

            try:
                face_resized = cv2.resize(face, FACE_SIZE)
            except:
                continue

            filename = user_faces_dir / f"face_{saved_count + 1}.png"
            cv2.imwrite(str(filename), face_resized)
            saved_count += 1

            yield 1  # notify progress update

        cv2.waitKey(20)

    cam.release()
    cv2.destroyAllWindows()


def _gather_training_data() -> Tuple[List[np.ndarray], List[int], dict]:
    faces = []
    labels = []
    label_map = {}
    reverse_map = {}
    current_label = 0

    for user_folder in sorted(BIOMETRIC_DIR.iterdir()):
        if not user_folder.is_dir():
            continue

        faces_dir = user_folder / "faces"
        if not faces_dir.exists():
            continue

        user_id = user_folder.name
        label_map[current_label] = user_id
        reverse_map[user_id] = current_label

        for img_path in faces_dir.glob("*.png"):
            img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue

            img_resized = cv2.resize(img, FACE_SIZE)
            faces.append(img_resized)
            labels.append(current_label)

        current_label += 1

    return faces, labels, label_map


def train_lbph_recognizer(model_path: Path = BIOMETRIC_DIR / "lbph_model.yml"):
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


def predict_face(threshold: float = 60.0) -> Tuple[Optional[str], float]:
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
    face = gray[y:y+h, x:x+w]
    face_resized = cv2.resize(face, FACE_SIZE)

    label, confidence = recognizer.predict(face_resized)
    user_id = label_map.get(str(label)) or label_map.get(label)

    if user_id is None or confidence > threshold:
        return None, confidence

    return user_id, confidence
