import customtkinter as ctk
from tkinter import messagebox, Toplevel
from datetime import datetime
from typing import Optional
from threading import Thread
from app import AuthSystem
from biometric.facial import capture_and_save_face_samples, train_lbph_recognizer
try:
    from biometric import facial as _facial_module  # type: ignore
    _HAS_STREAM_CAPTURE = hasattr(_facial_module, "open_camera_and_capture")
except Exception:
    _facial_module = None
    _HAS_STREAM_CAPTURE = False


class RegistrationPage(ctk.CTkFrame):

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.auth: AuthSystem = controller.auth
        self.grid(row=0, column=0, sticky="nsew")

        # runtime state
        self.current_user_id: Optional[str] = None
        self.biometric_captured = False
        self.biometric_choice = "Face"

        # UI
        self.configure(fg_color="#f5f5f5")
        self._build_ui()

    # -------------------- UI Setup --------------------
    def _build_ui(self):
        ctk.CTkLabel(
            self,
            text="Register New User",
            font=ctk.CTkFont(size=28, weight="bold")
        ).pack(pady=(30, 15))

        form_card = ctk.CTkFrame(self, corner_radius=15, fg_color="white")
        form_card.pack(padx=40, pady=20, fill="both", expand=False)

        self.name_entry = self._add_entry(form_card, "Full Name")
        self.dob_entry = self._add_entry(form_card, "DOB (YYYY-MM-DD)")

        self.gender_var = ctk.StringVar(value="Select Gender")
        self.gender_combo = ctk.CTkComboBox(
            form_card,
            values=["Male", "Female", "Other"],
            variable=self.gender_var,
            state="readonly"
        )
        self.gender_combo.pack(pady=10, padx=20)

        self.email_entry = self._add_entry(form_card, "Email")
        self.password_entry = self._add_entry(form_card, "Password", show="*")

        self.biometric_var = ctk.StringVar(value="Face")
        self.biometric_combo = ctk.CTkComboBox(
            form_card,
            values=["Face", "Fingerprint"],
            variable=self.biometric_var,
            state="readonly"
        )
        self.biometric_combo.pack(pady=10, padx=20)

        self._add_buttons(form_card)

    def _add_entry(self, parent, placeholder: str, show: Optional[str] = None):
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder, show=show)
        entry.pack(pady=10, padx=20)
        return entry

    def _add_buttons(self, parent):
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.pack(pady=15)

        self.register_btn = ctk.CTkButton(
            btn_frame,
            text="Register",
            width=130,
            command=self.handle_register
        )
        self.register_btn.grid(row=0, column=0, padx=10)

        self.capture_btn = ctk.CTkButton(
            btn_frame,
            text="Capture Biometric",
            width=160,
            command=self.handle_capture,
            state="disabled"
        )
        self.capture_btn.grid(row=0, column=1, padx=10)

        ctk.CTkButton(
            parent,
            text="Back to Login",
            fg_color="#888888",
            hover_color="#666666",
            command=lambda: self.controller.show_frame("LoginPage")
        ).pack(pady=10)

    # -------------------- Registration --------------------
    def handle_register(self):
        name = self.name_entry.get().strip()
        dob = self.dob_entry.get().strip()
        gender = self.gender_var.get()
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        self.biometric_choice = self.biometric_var.get()

        # validations
        if not all([name, dob, gender, email, password]) or gender == "Select Gender":
            messagebox.showerror("Validation", "All fields are required")
            return

        if not self._validate_dob(dob):
            messagebox.showerror("Validation", "DOB must be in YYYY-MM-DD format")
            return

        if not self._validate_email(email):
            messagebox.showerror("Validation", "Invalid email format")
            return

        if not self._validate_password(password):
            messagebox.showerror(
                "Validation",
                "Password must be at least 8 characters long and contain letters and digits"
            )
            return

        # register user via auth system
        user_id = self.auth.register_user(
            name=name,
            dob=dob,
            gender=gender,
            email=email,
            password=password,
            biometric_type=self.biometric_choice
        )

        if not user_id:
            messagebox.showerror("Registration Failed", "A user with this email already exists")
            return

        self.current_user_id = user_id
        self.biometric_captured = False
        self.capture_btn.configure(state="normal")

        messagebox.showinfo(
            "Registration Successful",
            f"User created successfully.\nAssigned ID: {user_id}\nProceed with biometric capture."
        )

    # -------------------- Biometric Capture --------------------
    def handle_capture(self):
        if self.current_user_id is None:
            messagebox.showerror("Error", "Please register before capturing biometric data")
            return

        if self.biometric_choice == "Face":
            # start background capture + training thread
            self._start_face_capture_thread()
        else:
            # fingerprint capture handled synchronously through auth
            self._capture_fingerprint()

    def _start_face_capture_thread(self):
        """Show progress modal and start background thread that captures and trains face model."""
        self.progress_modal = Toplevel(self)
        self.progress_modal.title("Facial Training")
        self.progress_modal.geometry("420x150")
        self.progress_modal.transient(self)
        self.progress_modal.grab_set()

        ctk.CTkLabel(
            self.progress_modal,
            text="Capturing facial samples and training recognizer...",
            font=ctk.CTkFont(size=14)
        ).pack(pady=(12, 6), padx=12)

        # progress bar
        self.progress_bar = ctk.CTkProgressBar(self.progress_modal)
        self.progress_bar.set(0.0)
        self.progress_bar.pack(pady=(6, 12), padx=20, fill="x")

        # subtle status label
        self._status_label = ctk.CTkLabel(self.progress_modal, text="Starting capture...")
        self._status_label.pack(pady=(0, 8))

        # run capture and training in background
        Thread(target=self._capture_and_train_face, daemon=True).start()

    def _capture_and_train_face(self):
        total_steps = 5
        saved_samples = 0

        try:
            if _HAS_STREAM_CAPTURE and _facial_module is not None:
                # Use streaming capture generator exposed by newer biometric module.
                gen = getattr(_facial_module, "open_camera_and_capture")(self.current_user_id, total_steps)
                for i, _ in enumerate(gen):
                    saved_samples += 1
                    progress = (i + 1) / total_steps
                    # update UI from main thread
                    self.progress_bar.after(0, lambda p=progress: self.progress_bar.set(p))
                    self._status_label.after(0, lambda s=f"Captured {i + 1}/{total_steps} samples": self._status_label.configure(text=s))
            else:
                # Fallback: call capture_and_save_face_samples(samples=1) repeatedly
                for i in range(total_steps):
                    saved_count, _ = capture_and_save_face_samples(self.current_user_id, samples=1)
                    saved_samples += saved_count
                    progress = (i + 1) / total_steps
                    self.progress_bar.after(0, lambda p=progress: self.progress_bar.set(p))
                    self._status_label.after(0, lambda s=f"Captured {i + 1}/{total_steps} samples": self._status_label.configure(text=s))

            # after capture, if any samples saved, train model
            if saved_samples > 0:
                self._status_label.after(0, lambda: self._status_label.configure(text="Training recognizer..."))
                # training can be somewhat heavy; run and then update UI
                trained = train_lbph_recognizer()
                if trained is False:
                    # training failed but capture succeeded
                    self.progress_modal.after(0, lambda: self.progress_modal.destroy())
                    self.register_btn.after(0, lambda: self.register_btn.configure(state="normal"))
                    self.capture_btn.after(0, lambda: self.capture_btn.configure(state="normal"))
                    messagebox.showwarning("Partial Success", "Captured samples but training failed.")
                    return

                # mark success on UI thread
                self.biometric_captured = True
                self.progress_modal.after(0, lambda: self.progress_modal.destroy())
                self.capture_btn.after(0, lambda: self.capture_btn.configure(state="disabled"))
                self.register_btn.after(0, lambda: self.register_btn.configure(state="disabled"))
                messagebox.showinfo("Success", "Facial biometric samples captured and trained successfully")
                # auto login on main thread
                self.after(0, self._auto_login)
            else:
                # no samples captured
                self.progress_modal.after(0, lambda: self.progress_modal.destroy())
                messagebox.showerror("Error", "Failed to capture facial biometric data")
        except Exception as exc:
            # ensure progress modal closed and buttons re-enabled
            try:
                self.progress_modal.after(0, lambda: self.progress_modal.destroy())
            except Exception:
                pass
            self.capture_btn.after(0, lambda: self.capture_btn.configure(state="normal"))
            messagebox.showerror("Error", f"Face capture failed: {exc}")

    def _capture_fingerprint(self):
        try:
            response = self.auth.capture_fingerprint_data(self.current_user_id)
        except Exception as e:
            messagebox.showerror("Error", f"Fingerprint capture failed: {e}")
            return

        if isinstance(response, str) and "captured" in response.lower():
            self.biometric_captured = True
            self.capture_btn.configure(state="disabled")
            self.register_btn.configure(state="disabled")
            messagebox.showinfo("Success", "Fingerprint biometric captured successfully")
            self._auto_login()
        else:
            # show whatever message the auth returned
            messagebox.showerror("Error", response if isinstance(response, str) else "Fingerprint capture failed")

    # -------------------- Auto Login --------------------
    def _auto_login(self):
        """Automatically log in user after successful biometric capture."""
        if self.current_user_id and self.biometric_captured:
            # controller is responsible for handling post login redirect
            try:
                self.controller.on_login_success(self.current_user_id)
            except Exception:
                # swallow; controller may not have that method
                pass

    # -------------------- Validation Utilities --------------------
    def _validate_dob(self, dob: str) -> bool:
        try:
            datetime.strptime(dob, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def _validate_email(self, email: str) -> bool:
        import re
        pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        return re.match(pattern, email) is not None

    def _validate_password(self, password: str) -> bool:
        return len(password) >= 8 and any(c.isdigit() for c in password) and any(c.isalpha() for c in password)
