import hashlib
from pathlib import Path
from biometric import facial
from utils.helpers import (
    load_users, save_users, generate_user_id, create_user_folder,
    get_user_fingerprint_path, save_ehr_for_user, load_user_ehr
)

# Admin credentials
ADMIN_USERNAME = "Admin"
ADMIN_PASSWORD = "Admin@123"


def is_admin(username, password):
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


class AuthSystem:
    def __init__(self):
        self.users = load_users()
        self.active_session = None

    # -----------------------------------------------------------
    # USER REGISTRATION
    # -----------------------------------------------------------
    def register_user(self, name, dob, gender, email, password, biometric_type="face"):
        # Prevent duplicates
        for uid, info in self.users.items():
            if info.get("email", "").strip().lower() == email.strip().lower():
                return None

        # Generate new user ID
        user_id = generate_user_id()

        # Create folder for biometric data
        create_user_folder(user_id)

        # Hash password for safe storage
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()

        # Store user details
        self.users[user_id] = {
            "name": name.strip(),
            "dob": dob.strip(),
            "gender": gender,
            "email": email.strip(),
            "password": hashed_pw,
            "biometric_type": biometric_type
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
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()

        # Admin login check
        if is_admin(username_or_email, password):
            self.active_session = "Admin"
            return True

        # Normal user login
        for uid, info in self.users.items():
            if username_or_email in (uid, info.get("email")):
                if info.get("password") == hashed_pw:
                    self.active_session = uid
                    return True

        return False

    # -----------------------------------------------------------
    # FACIAL LOGIN
    # -----------------------------------------------------------
    def login_facial(self, threshold=70.0):
        user_id, conf = facial.predict_face(threshold)

        if user_id:
            self.active_session = user_id
            return user_id, f"Facial login successful. Confidence {conf:.2f}"

        if conf == float("inf"):
            return None, "Recognizer not trained or no face detected"

        return None, f"No matching user found. Confidence {conf:.2f}"

    # -----------------------------------------------------------
    # FINGERPRINT LOGIN (SIMULATED)
    # -----------------------------------------------------------
    def login_fingerprint(self):
        """
        Looks for any stored fingerprint and matches it.
        Simulated because no real device integration.
        """
        temp_capture = Path("data/biometric/temp_fp.png")
        temp_capture.parent.mkdir(parents=True, exist_ok=True)
        temp_capture.touch(exist_ok=True)

        for uid, info in self.users.items():
            stored = info.get("fingerprint_path")
            if stored and Path(stored).exists():
                self.active_session = uid
                temp_capture.unlink(missing_ok=True)
                return uid, "Fingerprint login successful (simulated)"

        temp_capture.unlink(missing_ok=True)
        return None, "Fingerprint not recognized"

    # -----------------------------------------------------------
    # USER PROFILE FETCH  (THIS FIXES YOUR CURRENT CRASH)
    # -----------------------------------------------------------
    def get_user_profile(self, user_id):
        """
        Required by main_window, login_page, dashboard.
        """
        return self.users.get(user_id)

    # -----------------------------------------------------------
    # ADMIN UPLOAD EHR
    # -----------------------------------------------------------
    def admin_upload_ehr(self, target_user_id, file_path):
        if self.active_session != "Admin":
            raise PermissionError("Only Admin can upload EHR files")
        return save_ehr_for_user(target_user_id, file_path)

    # -----------------------------------------------------------
    # USER EHR
    # -----------------------------------------------------------
    def get_user_ehr_files(self, user_id):
        return load_user_ehr(user_id)

    # -----------------------------------------------------------
    # GET ALL USERS
    # -----------------------------------------------------------
    def get_all_users(self):
        return self.users
