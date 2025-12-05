import cv2
import numpy as np
from pathlib import Path

# Simple capture function that writes the captured frame to a given path
def capture_fingerprint(save_path: Path) -> bool:
    """
    Open webcam, show preview, press 'c' to capture fingerprint image, 'q' to quit.
    Saves the captured frame to save_path and returns True on success.
    """
    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        print("Cannot open camera for fingerprint capture")
        return False

    saved = False
    while True:
        ret, frame = cam.read()
        if not ret:
            continue
        cv2.imshow("Fingerprint Capture - press c to capture, q to quit", frame)
        key = cv2.waitKey(1)
        if key == ord("c"):
            # convert to grayscale and write
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            cv2.imwrite(str(save_path), gray)
            saved = True
            break
        elif key == ord("q"):
            saved = False
            break

    cam.release()
    cv2.destroyAllWindows()
    return saved


def compare_fingerprint(stored_path: Path, live_path: Path, threshold: float = 30.0) -> bool:
    """
    Compare two fingerprint images by resizing, taking absolute difference and computing mean.
    Returns True if mean difference is below threshold.
    """
    a = cv2.imread(str(stored_path), cv2.IMREAD_GRAYSCALE)
    b = cv2.imread(str(live_path), cv2.IMREAD_GRAYSCALE)
    if a is None or b is None:
        return False

    a_resized = cv2.resize(a, (300, 300))
    b_resized = cv2.resize(b, (300, 300))
    diff = cv2.absdiff(a_resized, b_resized)
    score = float(np.mean(diff))
    # lower score is better
    return score < threshold
