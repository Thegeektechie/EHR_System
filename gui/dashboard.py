# gui/dashboard.py

"""
Modern Dashboard for Admin and Users with validated EHR uploads and blockchain logging.
Features:
- Admin: list users, upload/validate EHR, edit EHR manually, download, export all EHRs
- User: view profile, preview latest EHR rendered as friendly fields, view/download files
- PDF viewer renders pages to images using pdf2image (poppler required)
- Blockchain log shown as hashed summary with a "Show" button to view full log entry
- Responsive arrangement using fill and expand where possible
"""

import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

import customtkinter as ctk
from tkinter import messagebox, filedialog

from utils.helpers import load_users, save_users, save_ehr_for_user, load_user_ehr, EHR_DIR
from blockchain.logger import BlockchainLogger


# Optional dependencies for PDF rendering
try:
    from pdf2image import convert_from_path
    from PIL import Image, ImageTk
    PDF_IMAGES_AVAILABLE = True
except Exception:
    PDF_IMAGES_AVAILABLE = False

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

        # Blockchain logger (ledger)
        self.blockchain_logger = BlockchainLogger()

        # Keep references to PhotoImage objects for PDF previews to avoid GC
        self._image_refs: List[ImageTk.PhotoImage] = []

        # Base layout
        self.grid(row=0, column=0, sticky="nsew")
        self.configure(fg_color="#f5f5f5")

        # Top controls area
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=(12, 8))

        self.title_label = ctk.CTkLabel(top_frame, text="Dashboard",
                                        font=ctk.CTkFont(size=26, weight="bold"))
        self.title_label.grid(row=0, column=0, sticky="w")

        # Admin area (right side)
        self.admin_actions_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        self.admin_actions_frame.grid(row=0, column=1, sticky="e")

        self.download_all_btn = ctk.CTkButton(
            self.admin_actions_frame, text="Export All EHRs",
            command=self.download_all_users_ehr, width=160
        )
        # shown only in admin mode

        self.view_ledger_btn = ctk.CTkButton(
            self.admin_actions_frame, text="View Ledger",
            command=self.open_blockchain_overview, width=120
        )
        # ledger view available to admin and users; admin will also see export

        # Info label (below)
        self.info_label = ctk.CTkLabel(self, text="No user selected", font=ctk.CTkFont(size=14))
        self.info_label.pack(padx=20, anchor="w", pady=(4, 8))

        # Container for list/profile/logs
        self.table_frame = ctk.CTkFrame(self, fg_color="white", corner_radius=12)
        self.table_frame.pack(padx=20, pady=10, fill="both", expand=True)

        # Footer with logout
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(8, 16))
        self.logout_btn = ctk.CTkButton(footer, text="Logout", fg_color="#ff5c5c",
                                        hover_color="#ff1f1f", width=120, command=self.logout)
        self.logout_btn.pack(side="right")

    # --------------------- Admin Methods ---------------------
    def enable_admin_mode(self):
        """Enable admin UI elements and refresh table"""
        self.is_admin = True
        self.title_label.configure(text="Admin Dashboard")
        self.info_label.configure(text="Manage users and records")
        # show admin controls
        self.download_all_btn.grid(row=0, column=0, padx=(6, 8))
        self.view_ledger_btn.grid(row=0, column=1, padx=(0, 8))
        self.refresh_admin_table()

    def refresh_admin_table(self):
        """Render table of users with actions"""
        for w in self.table_frame.winfo_children():
            w.destroy()

        users = load_users()
        if not users:
            ctk.CTkLabel(self.table_frame, text="No users available").pack(pady=20)
            return

        # Header row
        header = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        header.pack(fill="x", pady=6, padx=8)
        headings = ["User ID", "Name", "DOB", "Latest EHR", "Actions"]
        for i, h in enumerate(headings):
            ctk.CTkLabel(header, text=h, width=140, anchor="w").grid(row=0, column=i, padx=4)

        # Responsive rows
        for uid, user in users.items():
            row = ctk.CTkFrame(self.table_frame, fg_color="#f7fafc", corner_radius=8)
            row.pack(fill="x", padx=8, pady=4)

            display_uid = str(uid).zfill(5)
            ctk.CTkLabel(row, text=display_uid, width=120, anchor="w").grid(row=0, column=0, padx=4)
            ctk.CTkLabel(row, text=user.get("name", ""), width=180, anchor="w").grid(row=0, column=1, padx=4)
            ctk.CTkLabel(row, text=user.get("dob", ""), width=120, anchor="w").grid(row=0, column=2, padx=4)

            files = load_user_ehr(uid)
            last_file_path = files[-1] if files else None

            # Last EHR: show filename and a View button (not entire path)
            last_file_frame = ctk.CTkFrame(row, fg_color="transparent")
            last_file_frame.grid(row=0, column=3, padx=4)
            if last_file_path:
                fname = Path(last_file_path).name
                ctk.CTkLabel(last_file_frame, text=fname, anchor="w", width=220).pack(side="left", padx=(0, 6))
                ctk.CTkButton(last_file_frame, text="View", width=70,
                              command=lambda p=last_file_path, u=uid: self.view_ehr_modal(u, p)).pack(side="left")
            else:
                ctk.CTkLabel(last_file_frame, text="None", anchor="w", width=220).pack(side="left")

            # Actions: Edit, Download, Upload, Delete
            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.grid(row=0, column=4, padx=6)

            ctk.CTkButton(actions, text="Edit", width=80,
                          command=lambda u=uid: self.open_edit_ehr_modal(u)).pack(side="left", padx=3)

            ctk.CTkButton(actions, text="Download", width=80,
                          command=lambda u=uid: self.admin_download_latest_ehr(u)).pack(side="left", padx=3)

            ctk.CTkButton(actions, text="Upload", width=80,
                          command=lambda u=uid: self.upload_ehr_for_user(u)).pack(side="left", padx=3)

            ctk.CTkButton(actions, text="Delete", width=80, fg_color="#ff5c5c",
                          hover_color="#ff1f1f", command=lambda u=uid: self.delete_user(u)).pack(side="left", padx=3)

    def upload_ehr_for_user(self, user_id: str):
        """Admin uploads EHR file. PDFs get rendered using pdf2image when viewing."""
        file_path = filedialog.askopenfilename(
            title="Select EHR File",
            filetypes=[("EHR Files", "*.json *.txt *.pdf"), ("JSON", "*.json"), ("Text", "*.txt"), ("PDF", "*.pdf")]
        )
        if not file_path:
            return

        ehr_obj = None
        if file_path.lower().endswith(".json"):
            try:
                with open(file_path, "r", encoding="utf-8") as fh:
                    ehr_obj = json.load(fh)
            except Exception as e:
                messagebox.showerror("Invalid JSON", f"Could not parse JSON: {e}")
                return
        else:
            # attempt to extract text and create minimal object
            extracted = self._extract_text_from_file(file_path)
            if not extracted:
                messagebox.showerror("Unsupported", "Could not extract text from file for validation.")
                return
            try:
                ehr_obj = json.loads(extracted)
            except Exception:
                ehr_obj = {"_raw_text": extracted}

        if not self._validate_ehr_object(ehr_obj):
            messagebox.showerror("Invalid EHR", "Uploaded file is missing required EHR fields.")
            return

        saved = save_ehr_for_user(user_id, file_path)
        self.blockchain_logger.log_event(user_id=user_id, action="EHR_FILE_UPLOADED", metadata={"file": saved})
        messagebox.showinfo("Success", f"EHR uploaded for User {str(user_id).zfill(5)}")
        self.refresh_admin_table()

        # If the currently logged in user is the same user, refresh their profile
        if self.user_id == user_id and not self.is_admin:
            self.render_user_profile()

    def admin_download_latest_ehr(self, user_id: str):
        """Admin downloads the latest EHR file for a user to a chosen location."""
        files = load_user_ehr(user_id)
        if not files:
            messagebox.showwarning("No files", "No EHR files for this user.")
            return
        last = files[-1]
        target = filedialog.asksaveasfilename(title="Save EHR as", initialfile=Path(last).name)
        if not target:
            return
        try:
            shutil.copy(last, target)
            self.blockchain_logger.log_event(user_id=user_id, action="ADMIN_DOWNLOADED_EHR", metadata={"file": target})
            messagebox.showinfo("Saved", f"EHR copied to {target}")
        except Exception as e:
            messagebox.showerror("Failed", f"Copy failed: {e}")

    def download_all_users_ehr(self):
        """Export all users' EHRs as zip file."""
        users = load_users()
        if not users:
            messagebox.showwarning("No users", "There are no users to export.")
            return
        target = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("Zip", "*.zip")],
                                              title="Save combined EHR ZIP as")
        if not target:
            return
        tmpdir = tempfile.mkdtemp()
        try:
            for uid in users.keys():
                src = Path(EHR_DIR) / str(uid)
                if src.exists():
                    dest = Path(tmpdir) / str(uid)
                    shutil.copytree(src, dest)
            shutil.make_archive(base_name=Path(target).with_suffix(""), format="zip", root_dir=tmpdir)
            self.blockchain_logger.log_event(user_id="Admin", action="DOWNLOAD_ALL_EHRS", metadata={"out": target})
            messagebox.showinfo("Exported", f"All EHRs exported to {target}")
        except Exception as e:
            messagebox.showerror("Export failed", f"Failed to export: {e}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def delete_user(self, user_id: str):
        confirm = messagebox.askyesno("Delete user", f"Delete User {str(user_id).zfill(5)}?")
        if not confirm:
            return
        self.auth.users.pop(user_id, None)
        save_users(self.auth.users)
        self.blockchain_logger.log_event(user_id=user_id, action="USER_DELETED", metadata={})
        messagebox.showinfo("Deleted", "User removed.")
        self.refresh_admin_table()

    # ---------------------- Edit / Manual EHR Modal ----------------------
    def open_edit_ehr_modal(self, user_id: str):
        """Manual EHR editor modal for admin to create or edit EHRs."""
        modal = ctk.CTkToplevel(self)
        modal.title(f"Edit EHR - {str(user_id).zfill(5)}")
        modal.geometry("760x540")
        modal.grab_set()
        modal.transient(self)

        card = ctk.CTkFrame(modal, fg_color="white", corner_radius=12)
        card.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(card, text=f"Edit EHR - User {str(user_id).zfill(5)}",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=8, pady=(6, 6))

        # Prefill from latest file if present
        existing = {}
        files = load_user_ehr(user_id)
        if files:
            last_path = Path(files[-1])
            try:
                if last_path.suffix.lower() == ".json":
                    with open(last_path, "r", encoding="utf-8") as fh:
                        existing = json.load(fh)
                else:
                    # non-json fallback: keep raw_text
                    existing = {"_raw_text": self._extract_text_from_file(str(last_path)) or ""}
            except Exception:
                existing = {}

        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=8, pady=6)

        def make_row(label_text, init=""):
            lbl = ctk.CTkLabel(form, text=label_text, anchor="w")
            ent = ctk.CTkEntry(form, width=360)
            ent.insert(0, init)
            return lbl, ent

        lbl_name, ent_name = make_row("Name", existing.get("name", ""))
        lbl_name.grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ent_name.grid(row=0, column=1, sticky="w", padx=6, pady=6)

        lbl_addr, ent_addr = make_row("Address", existing.get("address", ""))
        lbl_addr.grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ent_addr.grid(row=1, column=1, sticky="w", padx=6, pady=6)

        lbl_dob, ent_dob = make_row("DOB (YYYY-MM-DD)", existing.get("dob", ""))
        lbl_dob.grid(row=2, column=0, sticky="w", padx=6, pady=6)
        ent_dob.grid(row=2, column=1, sticky="w", padx=6, pady=6)

        lbl_gen, ent_gen = make_row("Genotype", existing.get("genotype", ""))
        lbl_gen.grid(row=3, column=0, sticky="w", padx=6, pady=6)
        ent_gen.grid(row=3, column=1, sticky="w", padx=6, pady=6)

        lbl_bg, ent_bg = make_row("Blood group", existing.get("blood_group", ""))
        lbl_bg.grid(row=4, column=0, sticky="w", padx=6, pady=6)
        ent_bg.grid(row=4, column=1, sticky="w", padx=6, pady=6)

        lbl_med = ctk.CTkLabel(form, text="Medical history / Notes", anchor="w")
        lbl_med.grid(row=5, column=0, sticky="nw", padx=6, pady=6)
        txt_med = ctk.CTkTextbox(form, width=680, height=160)
        txt_med.insert("0.0", existing.get("medical_history", existing.get("_raw_text", "")))
        txt_med.grid(row=5, column=1, sticky="w", padx=6, pady=6)

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.pack(fill="x", padx=8, pady=8)

        def save_manual():
            ehr_obj = {
                "name": ent_name.get().strip(),
                "address": ent_addr.get().strip(),
                "dob": ent_dob.get().strip(),
                "genotype": ent_gen.get().strip(),
                "blood_group": ent_bg.get().strip(),
                "medical_history": txt_med.get("0.0", "end").strip()
            }
            if not self._validate_ehr_object(ehr_obj):
                messagebox.showerror("Invalid", "Please complete required EHR fields.")
                return
            try:
                tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8")
                json.dump(ehr_obj, tmp, indent=2)
                tmp.close()
                saved = save_ehr_for_user(user_id, tmp.name)
                self.blockchain_logger.log_event(user_id=user_id, action="EHR_MANUALLY_UPDATED", metadata={"file": saved})
                messagebox.showinfo("Saved", "EHR saved successfully.")
                modal.destroy()
                self.refresh_admin_table()
                # if same user is logged in (non-admin) refresh profile
                if self.user_id == user_id and not self.is_admin:
                    self.render_user_profile()
            except Exception as e:
                messagebox.showerror("Failed", f"Failed to save: {e}")

        ctk.CTkButton(btns, text="Save", fg_color="#10b981", hover_color="#059669", width=140,
                      command=save_manual).pack(side="right", padx=8)
        ctk.CTkButton(btns, text="Cancel", width=100, command=modal.destroy).pack(side="right", padx=8)

    # ---------------------- EHR Viewer (human friendly) ----------------------
    def view_ehr_modal(self, user_id: str, file_path: str):
        """Open modal that previews file in friendly format. PDFs render as images if dependencies available."""
        modal = ctk.CTkToplevel(self)
        modal.title(f"EHR Viewer - {str(user_id).zfill(5)}")
        modal.geometry("900x700")
        modal.grab_set()
        modal.transient(self)

        card = ctk.CTkFrame(modal, fg_color="white", corner_radius=12)
        card.pack(fill="both", expand=True, padx=10, pady=10)

        file_obj = Path(file_path)
        last_update = datetime.fromtimestamp(file_obj.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        header = ctk.CTkLabel(card, text=f"{file_obj.name}   Last updated: {last_update}",
                              font=ctk.CTkFont(size=14, weight="bold"))
        header.pack(anchor="w", padx=8, pady=(6, 4))

        # Two column layout: left - summary fields, right - full preview / PDF images
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=8, pady=6)

        left = ctk.CTkFrame(content, fg_color="#f7fafc", width=320, corner_radius=8)
        left.pack(side="left", fill="y", padx=(0, 8), pady=4)

        right = ctk.CTkFrame(content, fg_color="#ffffff", corner_radius=8)
        right.pack(side="left", fill="both", expand=True, padx=(0, 4), pady=4)

        # Load content
        suffix = file_obj.suffix.lower()
        parsed = {}
        raw_text = None
        try:
            if suffix == ".json":
                with open(file_obj, "r", encoding="utf-8") as fh:
                    parsed = json.load(fh)
            elif suffix in (".txt", ".md", ".csv"):
                with open(file_obj, "r", encoding="utf-8", errors="ignore") as fh:
                    raw_text = fh.read()
            elif suffix == ".pdf":
                # attempt to extract text; still will render as images below
                raw_text = self._extract_text_from_file(str(file_obj))
            else:
                raw_text = None
        except Exception:
            raw_text = None

        # Friendly summary on left
        def add_kv(label, value):
            ctk.CTkLabel(left, text=f"{label}:", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=8, pady=(8, 2))
            ctk.CTkLabel(left, text=value if value else "N/A", wraplength=300, anchor="w").pack(anchor="w", padx=8, pady=(0, 4))

        if isinstance(parsed, dict) and parsed:
            add_kv("Name", parsed.get("name", ""))
            add_kv("Address", parsed.get("address", ""))
            add_kv("DOB", parsed.get("dob", ""))
            add_kv("Genotype", parsed.get("genotype", ""))
            add_kv("Blood group", parsed.get("blood_group", ""))
        else:
            # fallback: show snippet of raw_text if present
            add_kv("Preview", (raw_text[:1000] + "...") if raw_text else "No structured data available")

        # Right side: full preview. If JSON, display mapped fields in nice layout; if PDF, render images
        if suffix == ".json" and isinstance(parsed, dict):
            # display as labeled sections (not raw JSON)
            right_inner = ctk.CTkFrame(right, fg_color="transparent")
            right_inner.pack(fill="both", expand=True, padx=8, pady=8)

            # Show each key in a readable block
            for i, (k, v) in enumerate(parsed.items()):
                lbl = ctk.CTkLabel(right_inner, text=str(k).replace("_", " ").capitalize(), font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
                lbl.grid(row=i*2, column=0, sticky="w", padx=4, pady=(6, 2))
                val = ctk.CTkLabel(right_inner, text=(json.dumps(v, indent=2, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)), anchor="w", wraplength=520)
                val.grid(row=i*2+1, column=0, sticky="w", padx=4, pady=(0, 6))
        elif suffix == ".pdf":
            # Render PDF pages to images if dependencies available
            if not PDF_IMAGES_AVAILABLE:
                ctk.CTkLabel(right, text="PDF rendering not available. Install pdf2image and pillow and ensure poppler is installed.").pack(padx=8, pady=8)
            else:
                # convert pages (may be heavy; limit pages)
                try:
                    self._image_refs.clear()
                    images = convert_from_path(str(file_obj), dpi=150, first_page=1, last_page=10)
                    # Display in a scrollable canvas
                    canvas_frame = ctk.CTkFrame(right, fg_color="transparent")
                    canvas_frame.pack(fill="both", expand=True, padx=4, pady=4)
                    canvas = ctk.CTkCanvas(canvas_frame)
                    canvas.pack(side="left", fill="both", expand=True)
                    scrollbar = ctk.CTkScrollbar(canvas_frame, orientation="vertical", command=canvas.yview)
                    scrollbar.pack(side="right", fill="y")
                    canvas.configure(yscrollcommand=scrollbar.set)
                    inner = ctk.CTkFrame(canvas)
                    canvas.create_window((0, 0), window=inner, anchor="nw")

                    for i, img in enumerate(images):
                        # downscale if very wide
                        max_w = 780
                        if img.width > max_w:
                            ratio = max_w / img.width
                            img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        self._image_refs.append(photo)
                        lbl = ctk.CTkLabel(inner, image=photo, text="")
                        lbl.pack(pady=8)
                    # update scroll region
                    inner.update_idletasks()
                    canvas.configure(scrollregion=canvas.bbox("all"))
                except Exception as e:
                    ctk.CTkLabel(right, text=f"Failed to render PDF: {e}").pack(padx=8, pady=8)
        else:
            # Text preview in right pane
            tb = ctk.CTkTextbox(right, width=760, height=420)
            if raw_text:
                tb.insert("0.0", raw_text)
            else:
                tb.insert("0.0", "No preview available for this file type.")
            tb.pack(fill="both", expand=True, padx=8, pady=8)

        # bottom actions
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=8, pady=8)
        def download_here():
            target = filedialog.asksaveasfilename(initialfile=file_obj.name, title="Save EHR as")
            if not target:
                return
            try:
                shutil.copy(str(file_obj), target)
                self.blockchain_logger.log_event(user_id=user_id, action="EHR_VIEW_DOWNLOAD", metadata={"file": target})
                messagebox.showinfo("Saved", f"File saved: {target}")
            except Exception as e:
                messagebox.showerror("Failed", f"Failed to save: {e}")

        ctk.CTkButton(actions, text="Download", width=140, command=download_here).pack(side="right", padx=8)
        ctk.CTkButton(actions, text="Close", width=100, command=modal.destroy).pack(side="right")

    # --------------------- User View / Logs / Profile ---------------------
    def set_user(self, user_id: str):
        """Set user view and render friendly profile and logs"""
        self.user_id = user_id
        self.is_admin = False
        name = self.auth.users.get(user_id, {}).get("name") if self.auth.users else None
        welcome = f"Welcome, {name}" if name else f"Welcome, User {str(user_id).zfill(5)}"
        self.title_label.configure(text="User Dashboard")
        self.info_label.configure(text=welcome)
        self.render_user_profile()
        self.refresh_user_log()

    def render_user_profile(self):
        """Render user profile and a friendly preview of latest EHR (not raw JSON)"""
        for w in self.table_frame.winfo_children():
            w.destroy()

        profile_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        profile_frame.pack(fill="x", padx=10, pady=10)

        user = self.auth.users.get(self.user_id, {}) if self.auth.users else {}
        name = user.get("name", "Unknown")
        dob = user.get("dob", "Unknown")
        email = user.get("email", "Unknown")

        info_card = ctk.CTkFrame(profile_frame, fg_color="#ffffff", corner_radius=8)
        info_card.pack(fill="x", pady=4, padx=4)

        ctk.CTkLabel(info_card, text="Name:", width=120, anchor="w").grid(row=0, column=0, padx=6, pady=6)
        ctk.CTkLabel(info_card, text=name, anchor="w").grid(row=0, column=1, padx=6, pady=6)
        ctk.CTkLabel(info_card, text="DOB:", width=120, anchor="w").grid(row=1, column=0, padx=6, pady=6)
        ctk.CTkLabel(info_card, text=dob, anchor="w").grid(row=1, column=1, padx=6, pady=6)
        ctk.CTkLabel(info_card, text="Email:", width=120, anchor="w").grid(row=2, column=0, padx=6, pady=6)
        ctk.CTkLabel(info_card, text=email, anchor="w").grid(row=2, column=1, padx=6, pady=6)

        # Latest EHR preview area
        files = load_user_ehr(self.user_id)
        if files:
            latest_path = Path(files[-1])
            preview_card = ctk.CTkFrame(self.table_frame, fg_color="#f3f4f6", corner_radius=8)
            preview_card.pack(fill="both", expand=True, padx=10, pady=8)

            ctk.CTkLabel(preview_card, text=f"Latest EHR: {latest_path.name}", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=8, pady=(8, 4))

            # Friendly rendering: if json show key/value table, else show text snippet
            try:
                if latest_path.suffix.lower() == ".json":
                    with open(latest_path, "r", encoding="utf-8") as fh:
                        parsed = json.load(fh)
                    # grid key value table
                    grid_frame = ctk.CTkFrame(preview_card, fg_color="transparent")
                    grid_frame.pack(fill="both", expand=True, padx=8, pady=8)
                    r = 0
                    for k in ("name", "address", "dob", "genotype", "blood_group"):
                        val = parsed.get(k, "N/A")
                        ctk.CTkLabel(grid_frame, text=f"{k.replace('_',' ').capitalize()}:", anchor="w", width=140).grid(row=r, column=0, sticky="w", padx=6, pady=4)
                        ctk.CTkLabel(grid_frame, text=str(val), anchor="w").grid(row=r, column=1, sticky="w", padx=6, pady=4)
                        r += 1
                    # medical history below
                    ctk.CTkLabel(grid_frame, text="Medical history / Notes:", anchor="w", font=ctk.CTkFont(weight="bold")).grid(row=r, column=0, sticky="nw", padx=6, pady=(8,4))
                    med_tb = ctk.CTkTextbox(grid_frame, width=760, height=160)
                    med_tb.insert("0.0", str(parsed.get("medical_history", "")))
                    med_tb.grid(row=r, column=1, padx=6, pady=(8,4))
                else:
                    txt = self._extract_text_from_file(str(latest_path)) or "Preview not available"
                    tb = ctk.CTkTextbox(preview_card, width=760, height=260)
                    tb.insert("0.0", txt[:3000])
                    tb.pack(fill="both", expand=True, padx=8, pady=8)
            except Exception as e:
                ctk.CTkLabel(preview_card, text=f"Preview failed: {e}").pack(padx=8, pady=8)

            # small actions: view and download
            act_frame = ctk.CTkFrame(preview_card, fg_color="transparent")
            act_frame.pack(fill="x", padx=8, pady=8)
            ctk.CTkButton(act_frame, text="View", width=100, command=lambda p=str(latest_path): self.view_ehr_modal(self.user_id, p)).pack(side="right", padx=6)
            ctk.CTkButton(act_frame, text="Download", width=100, command=lambda p=str(latest_path): self._download_file(p)).pack(side="right", padx=6)
        else:
            ctk.CTkLabel(self.table_frame, text="No EHR records available").pack(pady=8)

    def _download_file(self, src_path: str):
        """Utility to prompt and copy file"""
        src = Path(src_path)
        target = filedialog.asksaveasfilename(initialfile=src.name, title="Save file as")
        if not target:
            return
        try:
            shutil.copy(str(src), target)
            self.blockchain_logger.log_event(user_id=self.user_id or "Unknown", action="USER_DOWNLOADED_EHR", metadata={"file": target})
            messagebox.showinfo("Saved", f"Saved to {target}")
        except Exception as e:
            messagebox.showerror("Failed", f"Failed to save: {e}")

    def refresh_user_log(self):
        """Render blockchain events for logged in user below profile area."""
        # Append logs section
        logs = self.blockchain_logger.get_user_logs(self.user_id)
        # simple placement: place under frames already in table_frame
        ctk.CTkLabel(self.table_frame, text="").pack()  # spacing
        if not logs:
            ctk.CTkLabel(self.table_frame, text="No blockchain logs available").pack(pady=6)
            return

        header = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        header.pack(fill="x", pady=4, padx=6)
        for i, h in enumerate(["When", "Action", "Hash"]):
            ctk.CTkLabel(header, text=h, width=220, anchor="w").grid(row=0, column=i, padx=6)

        for entry in logs:
            row = ctk.CTkFrame(self.table_frame, fg_color="#f3f4f6", corner_radius=6)
            row.pack(fill="x", padx=6, pady=4)
            ts = entry.get("timestamp", "")
            # attempt friendly timestamp
            try:
                if isinstance(ts, (int, float)):
                    ts = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
            ctk.CTkLabel(row, text=str(ts), anchor="w", width=220).grid(row=0, column=0, padx=6)
            ctk.CTkLabel(row, text=entry.get("action", ""), anchor="w", width=220).grid(row=0, column=1, padx=6)
            # show hashed short summary and a button to view full metadata
            full_hash = entry.get("hash") or entry.get("current_hash") or entry.get("previous_hash") or ""
            short_hash = (str(full_hash)[:12] + "...") if full_hash else "n/a"
            ctk.CTkLabel(row, text=short_hash, anchor="w", width=220).grid(row=0, column=2, padx=6)
            ctk.CTkButton(row, text="Show", width=80, command=lambda e=entry: self._show_full_log_entry(e)).grid(row=0, column=3, padx=6)

    def _show_full_log_entry(self, entry: Dict[str, Any]):
        """Show full blockchain entry in modal."""
        modal = ctk.CTkToplevel(self)
        modal.title("Blockchain Log Entry")
        modal.geometry("700x500")
        modal.grab_set()
        modal.transient(self)

        card = ctk.CTkFrame(modal, fg_color="white", corner_radius=8)
        card.pack(fill="both", expand=True, padx=8, pady=8)

        tb = ctk.CTkTextbox(card, width=760, height=420)
        tb.pack(fill="both", expand=True, padx=8, pady=8)
        tb.insert("0.0", json.dumps(entry, indent=2, ensure_ascii=False))

        ctk.CTkButton(card, text="Close", width=100, command=modal.destroy).pack(pady=6)

    # ---------------------- Utilities ----------------------
    def _validate_ehr_object(self, ehr_obj: Dict[str, Any]) -> bool:
        """Basic structural EHR validation. Accepts raw_text containers when needed."""
        if not isinstance(ehr_obj, dict):
            return False
        # lower-case keys set for tolerant checks
        keys = set(k.lower() for k in ehr_obj.keys())
        for field in _REQUIRED_EHR_FIELDS:
            if field not in keys and field not in ehr_obj:
                return False
            # allow non-empty string or object/list
            if ehr_obj.get(field) in (None, "", []):
                return False
        return True

    def _extract_text_from_file(self, path: str) -> Optional[str]:
        """Extract text from txt or pdf (PyPDF2) as fallback for validation or plain preview."""
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
                for i, page in enumerate(reader.pages):
                    if i >= 5:
                        break
                    try:
                        text = page.extract_text() or ""
                        pages.append(text)
                    except Exception:
                        continue
                if not pages:
                    return None
                return "\n\n".join(pages)
            except Exception:
                return None
        return None

    def open_blockchain_overview(self):
        """Admin level overview of full ledger with ability to export or inspect entries."""
        modal = ctk.CTkToplevel(self)
        modal.title("Blockchain Ledger")
        modal.geometry("900x600")
        modal.grab_set()
        modal.transient(self)

        card = ctk.CTkFrame(modal, fg_color="white", corner_radius=10)
        card.pack(fill="both", expand=True, padx=8, pady=8)

        entries = []
        try:
            entries = self.blockchain_logger.get_all_logs()
        except Exception:
            # fallback to empty
            entries = []

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=6, pady=6)
        for i, h in enumerate(["When", "User", "Action", "Hash"]):
            ctk.CTkLabel(header, text=h, width=180, anchor="w").grid(row=0, column=i, padx=6)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=6, pady=6)
        # Scrollable list
        for e in entries:
            row = ctk.CTkFrame(body, fg_color="#f7fafc", corner_radius=6)
            row.pack(fill="x", pady=3)
            ts = e.get("timestamp")
            try:
                if isinstance(ts, (int, float)):
                    ts_f = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    ts_f = str(ts)
            except Exception:
                ts_f = str(ts)
            ctk.CTkLabel(row, text=ts_f, width=180, anchor="w").grid(row=0, column=0, padx=6)
            ctk.CTkLabel(row, text=str(e.get("user_id", "")), width=140, anchor="w").grid(row=0, column=1, padx=6)
            ctk.CTkLabel(row, text=str(e.get("action", "")), width=180, anchor="w").grid(row=0, column=2, padx=6)
            hval = (str(e.get("hash", "") )[:12] + "...") if e.get("hash") else "n/a"
            ctk.CTkLabel(row, text=hval, width=220, anchor="w").grid(row=0, column=3, padx=6)
            ctk.CTkButton(row, text="Inspect", width=100, command=lambda ev=e: self._show_full_log_entry(ev)).grid(row=0, column=4, padx=6)

        ctk.CTkButton(card, text="Close", width=120, command=modal.destroy).pack(side="right", padx=12, pady=8)

    def logout(self):
        """Logout and return to login page."""
        self.auth.active_session = None
        self.controller.show_frame("LoginPage")
