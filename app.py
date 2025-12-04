"""
app.py

Authentication system built on top of the OpenCV LBPH facial recognizer and
a simple fingerprint placeholder. Includes admin login and user EHR management.

Public methods used by GUI:
- register_user(name, dob, gender, email, password, biometric_type) -> user_id
- login_password(username_or_email, password) -> bool
- login_facial() -> (user_id or None, message)
- login_fingerprint() -> (user_id or None, message)
- admin_upload_ehr(target_user_id, file_path)
- get_user_ehr_files(user_id)

The AuthSystem automatically retrains the LBPH model when new face samples are added.
"""

import hashlib
from pathlib import Path
from biometric import facial
from utils.helpers import (
    load_users, save_users, generate_user_id, create_user_folder,
    get_user_faces_folder, get_user_fingerprint_path,
    save_ehr_for_user, load_user_ehr
)


# Admin credentials
ADMIN_USERNAME = "Admin"
ADMIN_PASSWORD = "Admin@123"


def is_admin(username, password):
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


class AuthSystem:
    def __init__(self):
        # Users dictionary loaded from disk
        self.users = load_users()
        self.active_session = None

    # ------------------- User Registration -------------------
    def register_user(self, name, dob, gender, email, password, biometric_type="face"):
        """
        Register a new user with required info and chosen biometric type.
        biometric_type: "face" or "fingerprint"
        Returns generated 5-digit user_id
        """
        # Check for duplicates
        for uid, info in self.users.items():
            if info.get("name", "").strip().lower() == name.strip().lower() and info.get("dob") == dob:
                return None

        # Generate unique 5-digit user_id
        user_id = generate_user_id()
        create_user_folder(user_id)

        # Hash password
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()

        # Store user info
        self.users[user_id] = {
            "name": name.strip(),
            "dob": dob.strip(),
            "gender": gender,
            "email": email.strip(),
            "password": hashed_pw,
            "biometric_type": biometric_type,
            "created_at": None  # optional, can set to datetime.utcnow().isoformat()
        }

        # Capture biometric
        if biometric_type == "face":
            facial.capture_and_save_face_samples(user_id, samples=5)
            facial.train_lbph_recognizer()
        elif biometric_type == "fingerprint":
            fp_path = get_user_fingerprint_path(user_id)
            fp_path.touch(exist_ok=True)

        save_users(self.users)
        return user_id

    # ------------------- Password Login -------------------
    def login_password(self, username_or_email, password):
        """
        Authenticate user by UserID/email + password
        Returns True if successful, False otherwise
        """
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        for uid, info in self.users.items():
            if username_or_email in (uid, info.get("email")):
                if info.get("password") == hashed_pw:
                    self.active_session = uid
                    return True
        if is_admin(username_or_email, password):
            self.active_session = "Admin"
            return True
        return False

    # ------------------- Facial Login -------------------
    def login_facial(self, threshold=70.0):
        """
        Capture a face and predict user using LBPH.
        Returns tuple (user_id or None, message)
        """
        user_id, conf = facial.predict_face(threshold)
        if user_id:
            self.active_session = user_id
            return user_id, f"Facial login successful. Confidence {conf:.2f}"
        if conf == float("inf"):
            return None, "Recognizer not trained or no capture"
        return None, f"No matching user found. Confidence {conf:.2f}"

    # ------------------- Fingerprint Login -------------------
    def login_fingerprint(self):
        """
        Placeholder for fingerprint login.
        Returns user_id if matched, None otherwise
        """
        temp_path = Path("data/biometric/temp_fp.png")
        temp_path.parent.mkdir(exist_ok=True)
        temp_path.touch(exist_ok=True)  # placeholder capture
        # TODO: Replace with actual fingerprint device capture and comparison
        for uid, info in self.users.items():
            stored = info.get("fingerprint_path")
            if stored and Path(stored).exists():
                self.active_session = uid
                temp_path.unlink(missing_ok=True)
                return uid, "Fingerprint login successful (simulated)"
        temp_path.unlink(missing_ok=True)
        return None, "Fingerprint did not match any stored user"

    # ------------------- Admin EHR -------------------
    def admin_upload_ehr(self, target_user_id, file_path):
        """
        Admin uploads an EHR file for a specific user
        """
        if self.active_session != "Admin":
            raise PermissionError("Only Admin can upload EHR files")
        return save_ehr_for_user(target_user_id, file_path)

    # ------------------- User EHR -------------------
    def get_user_ehr_files(self, user_id):
        """
        Return list of user's EHR files
        """
        return load_user_ehr(user_id)
