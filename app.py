import hashlib
from pathlib import Path
from biometric import facial
from utils.helpers import (
    load_users, save_users, generate_user_id, create_user_folder,
    get_user_fingerprint_path, save_ehr_for_user, load_user_ehr
)

# Administrator credentials
ADMIN_USERNAME = "Admin"
ADMIN_PASSWORD = "Admin@123"


def is_admin(username, password):
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


class AuthSystem:
    def __init__(self):
        # Load all users from storage
        self.users = load_users()
        self.active_session = None

    # -----------------------------------------------------------
    # REGISTRATION
    # -----------------------------------------------------------
    def register_user(self, name, dob, gender, email, password, biometric_type="face"):
        # Prevent duplicate email registration
        for uid, info in self.users.items():
            if info.get("email", "").strip().lower() == email.strip().lower():
                return None

        # Generate five digit user identifier
        user_id = str(generate_user_id())

        # Create folder for biometric data
        create_user_folder(user_id)

        # Securely hash password
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()

        # Save user information
        self.users[user_id] = {
            "name": name.strip(),
            "dob": dob.strip(),
            "gender": gender,
            "email": email.strip(),
            "password": hashed_pw,
            "biometric_type": biometric_type,
            "fingerprint_path": None
        }

        # Biometric capture
        if biometric_type == "face":
            facial.capture_and_save_face_samples(user_id, samples=5)
            facial.train_lbph_recognizer()

        elif biometric_type == "fingerprint":
            fp_path = get_user_fingerprint_path(user_id)
            fp_path.touch(exist_ok=True)
            self.users[user_id]["fingerprint_path"] = str(fp_path)

        save_users(self.users)
        return user_id

    # -----------------------------------------------------------
    # PASSWORD LOGIN
    # -----------------------------------------------------------
    def login_password(self, username_or_email, password):
        username_or_email = username_or_email.strip()

        # Administrator login
        if is_admin(username_or_email, password):
            self.active_session = "Admin"
            return True

        hashed_pw = hashlib.sha256(password.encode()).hexdigest()

        # Match either email or identifier
        for uid, info in self.users.items():
            if username_or_email == uid or username_or_email == info.get("email"):
                if info.get("password") == hashed_pw:
                    self.active_session = uid
                    return True
                return False

        return False

    # -----------------------------------------------------------
    # FACIAL LOGIN
    # -----------------------------------------------------------
    def login_facial(self, threshold=70.0):
        user_id, conf = facial.predict_face(threshold)

        if user_id is None:
            if conf == float("inf"):
                return None, "Camera error or the model is not trained"
            return None, f"Face did not match any user. Confidence {conf:.2f}"

        user_id = str(user_id)

        # Ensure user exists in storage
        if user_id not in self.users:
            return None, f"User not recognized. Confidence {conf:.2f}"

        self.active_session = user_id
        return user_id, f"Facial login successful. Confidence {conf:.2f}"

    # -----------------------------------------------------------
    # FINGERPRINT LOGIN (SIMULATED)
    # -----------------------------------------------------------
    def login_fingerprint(self):
        temp_fp = Path("data/biometric/temp_fp.png")
        temp_fp.parent.mkdir(parents=True, exist_ok=True)
        temp_fp.touch(exist_ok=True)

        # Simulated match
        for uid, info in self.users.items():
            fp = info.get("fingerprint_path")
            if fp and Path(fp).exists():
                self.active_session = uid
                temp_fp.unlink(missing_ok=True)
                return uid, "Fingerprint login successful"

        temp_fp.unlink(missing_ok=True)
        return None, "Fingerprint not recognized"

    # -----------------------------------------------------------
    # FETCH USER PROFILE
    # -----------------------------------------------------------
    def get_user_profile(self, user_id):
        return self.users.get(str(user_id))

    # -----------------------------------------------------------
    # ADMIN UPLOAD
    # -----------------------------------------------------------
    def admin_upload_ehr(self, target_user_id, file_path):
        if self.active_session != "Admin":
            raise PermissionError("Only the administrator can upload EHR files")
        return save_ehr_for_user(target_user_id, file_path)

    # -----------------------------------------------------------
    # FETCH USER EHR
    # -----------------------------------------------------------
    def get_user_ehr_files(self, user_id):
        return load_user_ehr(user_id)

    # -----------------------------------------------------------
    # LIST ALL USERS (ADMIN)
    # -----------------------------------------------------------
    def get_all_users(self):
        return self.users
