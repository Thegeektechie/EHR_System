import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List
import json
from utils.helpers import BIOMETRIC_DIR, LABEL_MAP_FILE

# Haar cascade for frontal face detection included with OpenCV package
FACE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
FACE_CASCADE = cv2.CascadeClassifier(FACE_CASCADE_PATH)

# Standard face image size used for training and prediction
FACE_SIZE = (200, 200)


def _detect_face_gray(gray_img: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """Detect a single largest face in the grayscale image and return (x,y,w,h) or None."""
    faces = FACE_CASCADE.detectMultiScale(gray_img, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        return None
    # choose the largest face detected
    faces = sorted(faces, key=lambda rect: rect[2] * rect[3], reverse=True)
    return faces[0]


def capture_face_sample(show_preview: bool = True) -> Optional[np.ndarray]:
    """
    Open the webcam, show a preview window and let the user press 'c' to capture a face.
    Returns the cropped grayscale face image resized to FACE_SIZE on success.
    Returns None on failure or if user quits with 'q'.
    """
    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        print("Error: cannot open camera")
        return None

    captured_face = None
    while True:
        ret, frame = cam.read()
        if not ret:
            continue

        # show detection rectangle for user feedback
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        face_rect = _detect_face_gray(gray)
        display = frame.copy()
        if face_rect is not None:
            x, y, w, h = face_rect
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)

        if show_preview:
            cv2.imshow("Face Capture - press c to capture, q to quit", display)

        key = cv2.waitKey(1)
        if key == ord("c"):
            # attempt to crop and return face
            if face_rect is None:
                # no face detected
                captured_face = None
                break
            x, y, w, h = face_rect
            face = gray[y:y + h, x:x + w]
            face_resized = cv2.resize(face, FACE_SIZE)
            captured_face = face_resized
            break
        elif key == ord("q"):
            captured_face = None
            break

    cam.release()
    cv2.destroyAllWindows()
    return captured_face


def capture_and_save_face_samples(user_id: str, samples: int = 5) -> Tuple[int, List[str]]:
    """
    Capture N face samples and save them as PNGs under data/biometric/<user_id>/faces/.
    Returns (saved_count, list_of_paths)
    During capture the function opens the camera repeatedly and asks user to press c for each sample.
    """
    user_faces_dir = BIOMETRIC_DIR / user_id / "faces"
    user_faces_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    saved_count = 0
    print(f"Starting face capture for user {user_id}. Capture {samples} samples. Press c to capture each sample.")

    while saved_count < samples:
        face_img = capture_face_sample(show_preview=True)
        if face_img is None:
            print("Failed to capture face. You can retry. Press q in the capture window to abort.")
            # ask user whether to retry or abort
            # For automation this function simply continues to next iteration
            continue
        filename = user_faces_dir / f"face_{saved_count + 1}.png"
        cv2.imwrite(str(filename), face_img)
        saved_paths.append(str(filename))
        saved_count += 1
        print(f"Saved sample {saved_count} to {filename}")

    return saved_count, saved_paths


def _gather_training_data() -> Tuple[List[np.ndarray], List[int], dict]:
    """
    Read all saved face images for all users under BIOMETRIC_DIR and return:
    - faces: list of 2D numpy arrays (grayscale)
    - labels: list of ints (label indices)
    - label_map: mapping from int label -> user_id
    """
    faces = []
    labels = []
    label_map = {}
    reverse_map = {}
    next_label = 0

    # user folders under biometric dir
    for user_folder in sorted(BIOMETRIC_DIR.iterdir()):
        if not user_folder.is_dir():
            continue
        faces_dir = user_folder / "faces"
        if not faces_dir.exists():
            continue
        user_id = user_folder.name
        # assign numeric label for this user id
        label_map[next_label] = user_id
        reverse_map[user_id] = next_label

        for img_path in faces_dir.glob("*.png"):
            img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            # ensure correct size
            img_resized = cv2.resize(img, FACE_SIZE)
            faces.append(img_resized)
            labels.append(next_label)
        next_label += 1

    return faces, labels, label_map


def train_lbph_recognizer(model_path: Path = BIOMETRIC_DIR / "lbph_model.yml"):
    """
    Train an LBPH recognizer on all saved face images and write model to disk.
    Also write label_map to LABEL_MAP_FILE.
    """
    faces, labels, label_map = _gather_training_data()
    if len(faces) == 0:
        print("No face training data found. Train aborted.")
        return False

    # Create LBPH recognizer
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces, np.array(labels, dtype=np.int32))
    recognizer.write(str(model_path))

    # save label map
    with open(LABEL_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(label_map, f, indent=2)

    print(f"Trained LBPH model with {len(set(labels))} label(s). Model saved to {model_path}")
    return True


def predict_face(threshold: float = 70.0) -> Tuple[Optional[str], float]:
    """
    Capture a face and predict the user id using the trained LBPH model.
    Returns a tuple (user_id_or_None, confidence). Lower confidence is better for LBPH.
    If predicted confidence is above threshold, returns (None, confidence).

    Confidence threshold default 70. Adjust for your camera and dataset.
    """
    model_path = BIOMETRIC_DIR / "lbph_model.yml"
    if not model_path.exists():
        print("LBPH model not found. Train the model first.")
        return None, float("inf")

    # load model and label map
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(str(model_path))

    with open(LABEL_MAP_FILE, "r", encoding="utf-8") as f:
        label_map = json.load(f)  # int label string -> user_id

    face_img = capture_face_sample(show_preview=True)
    if face_img is None:
        return None, float("inf")

    # predict
    label, confidence = recognizer.predict(face_img)
    # label_map keys are strings because json stores ints as keys converted to strings
    # convert to int safe
    user_id = label_map.get(str(label)) or label_map.get(label)
    if user_id is None:
        return None, confidence

    if confidence > threshold:
        # confidence too high means poor match
        return None, confidence

    return user_id, confidence
