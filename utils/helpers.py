# utils/helpers.py
import json
from pathlib import Path
from datetime import datetime
import shutil
import random
import string

# import for pdf text extraction
try:
    import PyPDF2
except Exception:
    PyPDF2 = None

# Paths
ROOT = Path.cwd()
DATA_DIR = ROOT / "data"
USERS_FILE = DATA_DIR / "users.json"
BIOMETRIC_DIR = DATA_DIR / "biometric"
LBPH_MODEL_FILE = BIOMETRIC_DIR / "lbph_model.yml"
LABEL_MAP_FILE = BIOMETRIC_DIR / "label_map.json"
EHR_DIR = DATA_DIR / "ehr_files"
BLOCKCHAIN_DIR = DATA_DIR / "blockchain"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
BIOMETRIC_DIR.mkdir(parents=True, exist_ok=True)
EHR_DIR.mkdir(parents=True, exist_ok=True)
BLOCKCHAIN_DIR.mkdir(parents=True, exist_ok=True)


# ------------------- User Management -------------------

def load_users() -> dict:
    """Load all users from JSON"""
    if USERS_FILE.exists():
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_users(users: dict):
    """Save users dict to disk"""
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)


def generate_user_id(name: str = "", dob: str = "") -> str:
    """
    Generate a unique 5 digit numeric user id.
    Ensures no collision with existing users.json.
    """
    users = load_users()
    attempts = 0
    while True:
        uid = f"{random.randint(0, 99999):05d}"  # zero padded 5 digits
        if uid not in users:
            return uid
        attempts += 1
        if attempts > 100000:
            # extremely unlikely, fallback to timestamp-based id
            return str(int(datetime.now().timestamp()))[-5:]


def create_user_folder(user_id: str) -> Path:
    """Create folders for biometric data for this user"""
    path = BIOMETRIC_DIR / user_id
    faces = path / "faces"
    faces.mkdir(parents=True, exist_ok=True)
    return path


# ------------------- EHR Management and Validation -------------------

_EHR_REQUIRED_FIELDS = {"name", "address", "genotype", "bloodgroup"}

def _text_contains_ehr_keywords(text: str) -> bool:
    """
    Heuristic check that text contains EHR keywords.
    Returns True when at least two required fields are present in the text.
    """
    t = text.lower()
    found = 0
    for kw in _EHR_REQUIRED_FIELDS:
        if kw in t:
            found += 1
    # require at least two keywords to reduce false positives
    return found >= 2


def _validate_json_ehr(path: Path) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Accept if JSON has any of required keys or nested structure containing them
        if isinstance(data, dict):
            keys = set(k.lower() for k in data.keys())
            if _EHR_REQUIRED_FIELDS & keys:
                return True
            # check nested fields as values
            flattened = json.dumps(data).lower()
            return _text_contains_ehr_keywords(flattened)
        return False
    except Exception:
        return False


def _validate_txt_ehr(path: Path) -> bool:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(8192)  # sample first 8kb
        return _text_contains_ehr_keywords(content)
    except Exception:
        return False


def _validate_pdf_ehr(path: Path) -> bool:
    if PyPDF2 is None:  # library not present
        # reject PDF. This avoids silent false positives.
        return False
    try:
        reader = PyPDF2.PdfReader(str(path))
        text = []
        # sample up to first three pages
        for i, page in enumerate(reader.pages):
            if i >= 3:
                break
            try:
                text.append(page.extract_text() or "")
            except Exception:
                pass
        joined = "\n".join(text)
        return _text_contains_ehr_keywords(joined)
    except Exception:
        return False


def validate_ehr_file(file_path: str) -> bool:
    """
    Validate if candidate file contains EHR details.
    Supports JSON, TXT, PDF. Returns True when validation passes.
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return False

    suffix = path.suffix.lower()
    if suffix in {".json"}:
        return _validate_json_ehr(path)
    if suffix in {".txt", ".md", ".csv"}:
        return _validate_txt_ehr(path)
    if suffix in {".pdf"}:
        return _validate_pdf_ehr(path)
    # other types are rejected by default
    return False


def save_ehr_for_user(user_id: str, file_path: str) -> str:
    """
    Copy a validated file into the user's EHR folder.
    Raises ValueError if validation fails.
    Returns the path to the saved file.
    """
    if not validate_ehr_file(file_path):
        raise ValueError("EHR validation failed. The uploaded file does not contain required EHR fields.")

    user_folder = EHR_DIR / user_id
    user_folder.mkdir(parents=True, exist_ok=True)
    dest_file = user_folder / Path(file_path).name
    shutil.copy(file_path, dest_file)
    return str(dest_file)


def load_user_ehr(user_id: str) -> list:
    """Return list of file names for a user's EHR folder"""
    user_folder = EHR_DIR / user_id
    if not user_folder.exists():
        return []
    # return full paths for convenience
    return [str(f) for f in sorted(user_folder.iterdir(), key=lambda p: p.stat().st_mtime)]


# ------------------- Admin Helper -------------------

def is_admin(username: str, password: str) -> bool:
    """Simple hard-coded admin check"""
    return username == "Admin" and password == "Admin@123"


# ------------------- Biometric Paths -------------------

def get_user_faces_folder(user_id: str) -> Path:
    """Return path to user's faces folder"""
    return BIOMETRIC_DIR / user_id / "faces"


def get_user_fingerprint_path(user_id: str) -> Path:
    """Return expected fingerprint path for user"""
    return BIOMETRIC_DIR / user_id / "fingerprint.png"


# ------------------- Per user blockchain helpers -------------------

def get_user_blockchain_path(user_id: str) -> Path:
    """Return file path for per user blockchain JSON"""
    f = BLOCKCHAIN_DIR / f"{user_id}.json"
    return f


def save_blockchain_for_user(user_id: str, event: dict):
    """
    Append an event to the user's blockchain file.
    This file is a list of blocks. Basic integrity fields included.
    """
    path = get_user_blockchain_path(user_id)
    chain = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as fh:
                chain = json.load(fh)
        except Exception:
            chain = []

    # compute previous hash simple
    prev_hash = chain[-1].get("current_hash") if chain else None
    event_record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "user_id": user_id,
        "event": event.get("event"),
        "action": event.get("action"),
        "metadata": event.get("metadata", {}),
        "previous_hash": prev_hash,
        # current hash is a simple content hash for traceability
        "current_hash": hashlib_sha256_hex(str(event.get("action")) + json.dumps(event.get("metadata", {})) + (prev_hash or ""))
    }
    chain.append(event_record)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(chain, fh, indent=2, ensure_ascii=False)
    return event_record


def load_blockchain_for_user(user_id: str) -> list:
    path = get_user_blockchain_path(user_id)
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return []


def hashlib_sha256_hex(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
