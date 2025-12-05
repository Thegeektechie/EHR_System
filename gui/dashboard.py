# gui/dashboard.py
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

import customtkinter as ctk
from tkinter import messagebox, filedialog

from utils.helpers import load_users, save_users, save_ehr_for_user, load_user_ehr, EHR_DIR
from blockchain.logger import BlockchainLogger

# Required fields for an EHR record to be considered valid
_REQUIRED_EHR_FIELDS = [
    "name",
    "address",
    "dob",
    "genotype",
    "blood_group",
    "medical_history"  # medical_history can be a string or object
]


class DashboardPage(ctk.CTkFrame):
    """Dashboard for Admin and Users with integrated blockchain logging and EHR validation"""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.auth = controller.auth
        self.user_id: Optional[str] = None
        self.is_admin = False

        # Blockchain logger
        self.blockchain_logger = BlockchainLogger()

        self.grid(row=0, column=0, sticky="nsew")
        self.configure(fg_color="#f5f5f5")

        # Top controls area
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=(16, 6))

        self.title_label = ctk.CTkLabel(
            top_frame,
            text="Dashboard",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        # Admin global actions container
        self.admin_actions_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        self.admin_actions_frame.grid(row=0, column=1, sticky="e")

        # Download all users EHRs (admin)
        self.download_all_btn = ctk.CTkButton(
            self.admin_actions_frame,
            text="Download All EHRs",
            command=self.download_all_users_ehr,
            width=160
        )
        # This will be shown only in admin mode

        # Info label
        self.info_label = ctk.CTkLabel(
            self,
            text="No user selected",
            font=ctk.CTkFont(size=16)
        )
        self.info_label.pack(pady=(0, 12), padx=20, anchor="w")

        # Table frame for user/admin views
        self.table_frame = ctk.CTkFrame(self, fg_color="white", corner_radius=15)
        self.table_frame.pack(padx=20, pady=10, fill="both", expand=True)

        # Footer logout
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(8, 20))
        self.logout_btn = ctk.CTkButton(
            footer,
            text="Logout",
            fg_color="#ff5c5c",
            hover_color="#ff1f1f",
            command=self.logout,
            width=120
        )
        self.logout_btn.pack(side="right")

    # --------------------- Admin Methods ---------------------

    def enable_admin_mode(self):
        """Switch to admin dashboard view and show admin controls"""
        self.is_admin = True
        self.title_label.configure(text="Admin Dashboard")
        self.info_label.configure(text="Manage users and their records")
        # show admin global button
        self.download_all_btn.grid(row=0, column=0, padx=(6, 0))
        self.refresh_admin_table()

    def refresh_admin_table(self):
        """Render table of all users and controls"""
        for w in self.table_frame.winfo_children():
            w.destroy()

        users = load_users()
        if not users:
            ctk.CTkLabel(self.table_frame, text="No users available").pack(pady=20)
            return

        # Header row
        header = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        header.pack(fill="x", pady=6, padx=6)
        headings = ["User ID", "Name", "DOB", "Last EHR", "Actions"]
        for i, h in enumerate(headings):
            ctk.CTkLabel(header, text=h, width=150, anchor="w").grid(row=0, column=i, padx=4)

        # User rows
        for uid, user in users.items():
            row = ctk.CTkFrame(self.table_frame, fg_color="#f7fafc", corner_radius=8)
            row.pack(fill="x", padx=6, pady=4)

            display_uid = str(uid).zfill(5)
            ctk.CTkLabel(row, text=display_uid, width=150, anchor="w").grid(row=0, column=0, padx=4)
            ctk.CTkLabel(row, text=user.get("name", ""), width=150, anchor="w").grid(row=0, column=1, padx=4)
            ctk.CTkLabel(row, text=user.get("dob", ""), width=150, anchor="w").grid(row=0, column=2, padx=4)

            files = load_user_ehr(uid)
            last_file_path = files[-1] if files else None
            # show filename + View button instead of long path
            last_file_frame = ctk.CTkFrame(row, fg_color="transparent")
            last_file_frame.grid(row=0, column=3, padx=4)
            if last_file_path:
                fname = Path(last_file_path).name
                ctk.CTkLabel(last_file_frame, text=fname, anchor="w", width=200).pack(side="left", padx=(0, 6))
                ctk.CTkButton(last_file_frame, text="View", width=70,
                              command=lambda p=last_file_path, u=uid: self.view_ehr_modal(u, p)).pack(side="left")
            else:
                ctk.CTkLabel(last_file_frame, text="None", anchor="w", width=200).pack(side="left")

            # Actions: Edit, Download, Upload, Delete
            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.grid(row=0, column=4, padx=6)

            ctk.CTkButton(
                actions, text="Edit EHR", width=90,
                command=lambda u=uid: self.open_edit_ehr_modal(u)
            ).pack(side="left", padx=3)

            ctk.CTkButton(
                actions, text="Download", width=90,
                command=lambda u=uid: self.admin_download_latest_ehr(u)
            ).pack(side="left", padx=3)

            ctk.CTkButton(
                actions, text="Upload", width=90,
                command=lambda u=uid: self.upload_ehr_for_user(u)
            ).pack(side="left", padx=3)

            ctk.CTkButton(
                actions, text="Delete", width=90,
                fg_color="#ff5c5c", hover_color="#ff1f1f",
                command=lambda u=uid: self.delete_user(u)
            ).pack(side="left", padx=3)

    def upload_ehr_for_user(self, user_id):
        """Admin uploads an EHR file only if it contains valid EHR structure."""
        file_path = filedialog.askopenfilename(
            title="Select EHR File",
            filetypes=[
                ("EHR Files", "*.json *.txt *.pdf"),
                ("JSON Files", "*.json"),
                ("Text Files", "*.txt"),
                ("PDF Files", "*.pdf")
            ]
        )
        if not file_path:
            return

        # Try reading as JSON first
        ehr_obj = None
        # If JSON
        if file_path.lower().endswith(".json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    ehr_obj = json.load(f)
            except Exception as e:
                messagebox.showerror("Invalid file", f"Failed to parse JSON: {e}")
                return
        else:
            # For txt or pdf we attempt simple validation via extractor
            extracted = self._extract_text_from_file(file_path)
            if not extracted:
                messagebox.showerror("Unsupported format", "Could not extract text from file for validation.")
                return
            # try to parse extracted text as JSON first
            try:
                ehr_obj = json.loads(extracted)
            except Exception:
                # fallback to heuristic; build a minimal object from extracted text
                ehr_obj = {"_raw_text": extracted}

        if not self._validate_ehr_object(ehr_obj):
            messagebox.showerror(
                "Invalid EHR",
                "Uploaded file does not contain required EHR fields. Upload rejected."
            )
            return

        saved = save_ehr_for_user(user_id, file_path)
        self.blockchain_logger.log_event(
            user_id=user_id,
            action="EHR_FILE_UPLOADED",
            metadata={"file": saved}
        )
        messagebox.showinfo("Success", f"EHR uploaded for User {str(user_id).zfill(5)}")
        self.refresh_admin_table()

    def admin_download_latest_ehr(self, user_id):
        """Admin downloads the latest EHR file for a user."""
        files = load_user_ehr(user_id)
        if not files:
            messagebox.showwarning("Download", "No EHR files found for this user")
            return
        last_file = files[-1]
        # Ask user where to save
        target = filedialog.asksaveasfilename(
            title="Save EHR as",
            initialfile=Path(last_file).name
        )
        if not target:
            return
        try:
            shutil.copy(last_file, target)
            self.blockchain_logger.log_event(
                user_id=user_id,
                action="ADMIN_DOWNLOADED_EHR",
                metadata={"file": target}
            )
            messagebox.showinfo("Download", f"EHR file saved to: {target}")
        except Exception as e:
            messagebox.showerror("Download failed", f"Failed to copy file: {e}")

    def download_all_users_ehr(self):
        """Download all users' EHR files as a single zip (admin)."""
        users = load_users()
        if not users:
            messagebox.showwarning("No users", "There are no users to export.")
            return

        target = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("Zip file", "*.zip")],
            title="Save combined EHR ZIP as"
        )
        if not target:
            return

        tmpdir = tempfile.mkdtemp()
        try:
            for uid in users.keys():
                src = Path(EHR_DIR) / str(uid)
                if src.exists():
                    dest = Path(tmpdir) / str(uid)
                    shutil.copytree(src, dest)
            shutil.make_archive(
                base_name=Path(target).with_suffix(""),
                format="zip",
                root_dir=tmpdir
            )
            self.blockchain_logger.log_event(
                user_id="Admin",
                action="DOWNLOAD_ALL_EHRS",
                metadata={"out": target}
            )
            messagebox.showinfo("Exported", f"All EHRs exported to {target}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Failed to export EHRs: {e}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def delete_user(self, user_id):
        confirm = messagebox.askyesno(
            "Delete User",
            f"Are you sure you want to delete User {str(user_id).zfill(5)}?"
        )
        if not confirm:
            return

        self.auth.users.pop(user_id, None)
        save_users(self.auth.users)

        self.blockchain_logger.log_event(
            user_id=user_id,
            action="USER_DELETED",
            metadata={}
        )
        messagebox.showinfo("Deleted", f"User {str(user_id).zfill(5)} removed.")
        self.refresh_admin_table()

    # ---------------------- Edit / Manual EHR Modal ----------------------

    def open_edit_ehr_modal(self, user_id: str):
        """Open a modal that allows admin to view or create EHR data manually for the user."""
        modal = ctk.CTkToplevel(self)
        modal.title(f"Edit EHR - User {str(user_id).zfill(5)}")
        modal.geometry("720x520")
        modal.grab_set()
        modal.transient(self)

        card = ctk.CTkFrame(modal, fg_color="white", corner_radius=12)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            card,
            text=f"Edit EHR for User {str(user_id).zfill(5)}",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=(8, 6), anchor="w", padx=12)

        existing = {}
        files = load_user_ehr(user_id)
        if files:
            last_path = Path(files[-1])
            try:
                with open(last_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = {}

        form_frame = ctk.CTkFrame(card, fg_color="transparent")
        form_frame.pack(fill="both", expand=True, padx=12, pady=8)

        def row_widgets(label_text, init_value=""):
            lbl = ctk.CTkLabel(form_frame, text=label_text, anchor="w")
            ent = ctk.CTkEntry(form_frame, width=320)
            ent.insert(0, init_value)
            return lbl, ent

        lbl_name, ent_name = row_widgets("Full name", existing.get("name", ""))
        lbl_name.grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ent_name.grid(row=0, column=1, sticky="w", padx=6, pady=6)

        lbl_address, ent_address = row_widgets("Address", existing.get("address", ""))
        lbl_address.grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ent_address.grid(row=1, column=1, sticky="w", padx=6, pady=6)

        lbl_dob, ent_dob = row_widgets("DOB (YYYY-MM-DD)", existing.get("dob", ""))
        lbl_dob.grid(row=2, column=0, sticky="w", padx=6, pady=6)
        ent_dob.grid(row=2, column=1, sticky="w", padx=6, pady=6)

        lbl_genotype, ent_genotype = row_widgets("Genotype", existing.get("genotype", ""))
        lbl_genotype.grid(row=3, column=0, sticky="w", padx=6, pady=6)
        ent_genotype.grid(row=3, column=1, sticky="w", padx=6, pady=6)

        lbl_blood, ent_blood = row_widgets("Blood group", existing.get("blood_group", ""))
        lbl_blood.grid(row=4, column=0, sticky="w", padx=6, pady=6)
        ent_blood.grid(row=4, column=1, sticky="w", padx=6, pady=6)

        lbl_med = ctk.CTkLabel(form_frame, text="Medical history / Notes", anchor="w")
        lbl_med.grid(row=5, column=0, sticky="nw", padx=6, pady=6)
        txt_med = ctk.CTkTextbox(form_frame, width=680, height=120)
        txt_med.insert("0.0", existing.get("medical_history", ""))
        txt_med.grid(row=5, column=1, sticky="w", padx=6, pady=6)

        buttons_frame = ctk.CTkFrame(card, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=12, pady=12)

        def save_manual_ehr():
            ehr_obj = {
                "name": ent_name.get().strip(),
                "address": ent_address.get().strip(),
                "dob": ent_dob.get().strip(),
                "genotype": ent_genotype.get().strip(),
                "blood_group": ent_blood.get().strip(),
                "medical_history": txt_med.get("0.0", "end").strip()
            }

            if not self._validate_ehr_object(ehr_obj):
                messagebox.showerror("Invalid EHR", "Please fill required EHR fields before saving.")
                return

            try:
                tmp = tempfile.NamedTemporaryFile(
                    mode="w", delete=False,
                    suffix=".json", encoding="utf-8"
                )
                json.dump(ehr_obj, tmp, indent=2)
                tmp.close()
                saved_path = save_ehr_for_user(user_id, tmp.name)
                self.blockchain_logger.log_event(
                    user_id=user_id, action="EHR_MANUALLY_UPDATED",
                    metadata={"file": saved_path}
                )
                messagebox.showinfo("Saved", f"EHR saved for user {str(user_id).zfill(5)}")
                modal.destroy()
                self.refresh_admin_table()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save EHR: {e}")

        ctk.CTkButton(
            buttons_frame, text="Save EHR",
            fg_color="#10b981", hover_color="#059669",
            command=save_manual_ehr, width=140
        ).pack(side="right", padx=8)
        ctk.CTkButton(
            buttons_frame, text="Cancel", width=100,
            command=modal.destroy
        ).pack(side="right", padx=8)

    # ---------------------- View EHR modal ----------------------

    def view_ehr_modal(self, user_id: str, file_path: str):
        """Open a modal to preview EHR file content and metadata"""
        modal = ctk.CTkToplevel(self)
        modal.title(f"EHR Viewer - User {str(user_id).zfill(5)}")
        modal.geometry("820x620")
        modal.grab_set()
        modal.transient(self)

        card = ctk.CTkFrame(modal, fg_color="white", corner_radius=12)
        card.pack(fill="both", expand=True, padx=12, pady=12)

        # Header
        file_obj = Path(file_path)
        last_update = datetime.fromtimestamp(file_obj.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        header_text = f"File: {file_obj.name}    Last updated: {last_update}"
        ctk.CTkLabel(card, text=header_text, font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=12, pady=(8, 6))

        # Content area
        content_frame = ctk.CTkFrame(card, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=12, pady=(2, 8))

        text_box = ctk.CTkTextbox(content_frame, width=760, height=420)
        text_box.pack(fill="both", expand=True)

        # Load and render content based on suffix
        try:
            suffix = file_obj.suffix.lower()
            if suffix == ".json":
                with open(file_obj, "r", encoding="utf-8") as f:
                    parsed = json.load(f)
                pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
                text_box.insert("0.0", pretty)
            elif suffix in (".txt", ".md", ".csv"):
                with open(file_obj, "r", encoding="utf-8", errors="ignore") as f:
                    text_box.insert("0.0", f.read())
            elif suffix == ".pdf":
                extracted = self._extract_text_from_file(str(file_obj))
                if extracted:
                    text_box.insert("0.0", extracted)
                else:
                    text_box.insert("0.0", "Unable to extract text from PDF. It may be scanned or require OCR.")
            else:
                text_box.insert("0.0", "Preview not supported for this file type.")
        except Exception as e:
            text_box.insert("0.0", f"Failed to read file: {e}")

        # Bottom actions: Download, Close
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=8)

        def download_here():
            target = filedialog.asksaveasfilename(initialfile=file_obj.name, title="Save EHR as")
            if not target:
                return
            try:
                shutil.copy(str(file_obj), target)
                self.blockchain_logger.log_event(user_id=user_id, action="EHR_VIEW_DOWNLOAD", metadata={"file": target})
                messagebox.showinfo("Saved", f"File saved to {target}")
            except Exception as e:
                messagebox.showerror("Failed", f"Failed to save file: {e}")

        ctk.CTkButton(actions, text="Download", width=140, command=download_here).pack(side="right", padx=8)
        ctk.CTkButton(actions, text="Close", width=100, command=modal.destroy).pack(side="right")

    # --------------------- User View / Logs ---------------------

    def set_user(self, user_id: str):
        """Set user view and render blockchain logs for user"""
        self.user_id = user_id
        self.is_admin = False
        self.title_label.configure(text="User Dashboard")
        self.info_label.configure(text=f"Welcome, User {str(user_id).zfill(5)}")
        self.refresh_user_log()

    def refresh_user_log(self):
        """Render blockchain events for logged in user"""
        for w in self.table_frame.winfo_children():
            w.destroy()

        logs = self.blockchain_logger.get_user_logs(self.user_id)
        if not logs:
            ctk.CTkLabel(self.table_frame, text="No blockchain logs available").pack(pady=20)
            return

        header = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        header.pack(fill="x", pady=2, padx=6)
        for i, h in enumerate(["Timestamp", "Action", "Details"]):
            ctk.CTkLabel(header, text=h, width=220, anchor="w").grid(row=0, column=i, padx=5)

        for entry in logs:
            row = ctk.CTkFrame(self.table_frame, fg_color="#f3f4f6", corner_radius=8)
            row.pack(fill="x", padx=6, pady=4)
            ctk.CTkLabel(row, text=str(entry.get("timestamp", "")), anchor="w", width=200).grid(row=0, column=0, padx=6)
            ctk.CTkLabel(row, text=entry.get("action", ""), anchor="w", width=200).grid(row=0, column=1, padx=6)
            ctk.CTkLabel(
                row,
                text=str(entry.get("metadata", "") or entry.get("details", "")),
                anchor="w", width=360
            ).grid(row=0, column=2, padx=6)

    # ---------------------- Utilities ----------------------

    def _validate_ehr_object(self, ehr_obj: Dict[str, Any]) -> bool:
        """Simple structural validation for EHR object."""
        if not isinstance(ehr_obj, dict):
            return False
        # accept raw text container that includes keys as lower case
        keys = set(k.lower() for k in ehr_obj.keys())
        for field in _REQUIRED_EHR_FIELDS:
            if field not in keys and field not in ehr_obj:
                return False
            if ehr_obj.get(field) in (None, "", []):
                return False
        return True

    def _extract_text_from_file(self, path: str) -> Optional[str]:
        """
        Extract readable text from txt and pdf files.
        PDF extraction uses PyPDF2. If not installed or extraction fails returns None.
        """
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix in (".txt", ".md", ".csv"):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                    return fh.read()
            except Exception:
                return None
        if suffix == ".pdf":
            try:
                import PyPDF2
            except Exception:
                return None
            try:
                reader = PyPDF2.PdfReader(str(p))
                pages = []
                # sample limited pages for performance
                for i, page in enumerate(reader.pages):
                    if i >= 5:
                        break
                    try:
                        txt = page.extract_text()
                        if txt:
                            pages.append(txt)
                    except Exception:
                        continue
                if not pages:
                    return None
                return "\n\n".join(pages)
            except Exception:
                return None
        return None

    def logout(self):
        """Logout and return to login page."""
        self.auth.active_session = None
        self.controller.show_frame("LoginPage")
