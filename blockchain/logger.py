import hashlib
import json
import time
from typing import Dict, Any, List
from pathlib import Path


REQUIRED_EHR_FIELDS = {
    "name",
    "address",
    "genotype",
    "blood_group",
    "dob",
    "gender",
    "medical_history",
    "allergies"
}


class BlockchainLogger:
    def __init__(self, ledger_path="data/ledger.json"):
        self.ledger_path = Path(ledger_path)
        self._ensure_ledger()

    # ------------------------------------------------------------------
    # Ledger File Management
    # ------------------------------------------------------------------

    def _ensure_ledger(self):
        """Ensure ledger file exists and is valid"""
        if not self.ledger_path.exists():
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.ledger_path, "w") as f:
                json.dump([], f, indent=4)

        else:
            try:
                with open(self.ledger_path, "r") as f:
                    json.load(f)
            except json.JSONDecodeError:
                with open(self.ledger_path, "w") as f:
                    json.dump([], f, indent=4)

    def _get_last_hash(self) -> str:
        try:
            with open(self.ledger_path, "r") as f:
                ledger = json.load(f)
            return ledger[-1]["hash"] if ledger else "GENESIS"
        except:
            return "GENESIS"

    def _calculate_hash(self, block: Dict[str, Any]) -> str:
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    # ------------------------------------------------------------------
    # EHR Validation
    # ------------------------------------------------------------------

    def validate_ehr_structure(self, ehr_json: Dict[str, Any]) -> bool:
        """
        Validate that an EHR file contains the required fields.
        Reject upload if EHR structure is incomplete.
        """
        if not isinstance(ehr_json, dict):
            return False

        provided_fields = set(ehr_json.keys())

        # Must contain all standard EHR fields
        return REQUIRED_EHR_FIELDS.issubset(provided_fields)

    def validate_ehr_file(self, file_path: str) -> bool:
        """
        Validate uploaded EHR JSON file.
        Return True only if file contains valid EHR record.
        """
        path = Path(file_path)

        if not path.exists():
            return False

        # Ensure file is JSON
        if path.suffix.lower() != ".json":
            return False

        try:
            with open(path, "r", encoding="utf8") as f:
                ehr_data = json.load(f)
        except:
            return False

        return self.validate_ehr_structure(ehr_data)

    # ------------------------------------------------------------------
    # Core Blockchain Logging
    # ------------------------------------------------------------------

    def log_event(self, user_id: str, action: str, metadata: Dict[str, Any]):
        """
        Log a blockchain event for admins and users.
        """
        block = {
            "timestamp": int(time.time()),
            "user_id": user_id,
            "action": action,
            "metadata": metadata,
            "prev_hash": self._get_last_hash()
        }

        block["hash"] = self._calculate_hash(block)

        with open(self.ledger_path, "r") as f:
            ledger: List[Dict[str, Any]] = json.load(f)

        ledger.append(block)

        with open(self.ledger_path, "w") as f:
            json.dump(ledger, f, indent=4)

    # ------------------------------------------------------------------
    # Read Operations
    # ------------------------------------------------------------------

    def get_user_logs(self, user_id: str):
        with open(self.ledger_path, "r") as f:
            ledger = json.load(f)
        return [entry for entry in ledger if entry["user_id"] == user_id]

    def get_all_logs(self):
        with open(self.ledger_path, "r") as f:
            return json.load(f)
