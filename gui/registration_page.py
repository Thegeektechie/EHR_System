import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from typing import Optional
from app import AuthSystem
from biometric.facial import capture_and_save_face_samples, train_lbph_recognizer


class RegistrationPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.auth: AuthSystem = controller.auth
        self.grid(row=0, column=0, sticky="nsew")
        self.current_user_id: Optional[str] = None
        self.biometric_captured = False
        self.biometric_choice = "Face"

        self.configure(fg_color="#f5f5f5")

        ctk.CTkLabel(
            self,
            text="Register New User",
            font=ctk.CTkFont(size=28, weight="bold")
        ).pack(pady=(30, 15))

        form_card = ctk.CTkFrame(self, corner_radius=15, fg_color="white")
        form_card.pack(padx=40, pady=20, fill="both", expand=False)

        # Full Name
        self.name_entry = ctk.CTkEntry(form_card, placeholder_text="Full Name")
        self.name_entry.pack(pady=10, padx=20)

        # DOB
        self.dob_entry = ctk.CTkEntry(form_card, placeholder_text="DOB (YYYY-MM-DD)")
        self.dob_entry.pack(pady=10, padx=20)

        # Gender
        self.gender_var = ctk.StringVar(value="Select Gender")
        self.gender_combo = ctk.CTkComboBox(
            form_card,
            values=["Male", "Female", "Other"],
            variable=self.gender_var,
            state="readonly"
        )
        self.gender_combo.pack(pady=10, padx=20)

        # Email
        self.email_entry = ctk.CTkEntry(form_card, placeholder_text="Email")
        self.email_entry.pack(pady=10, padx=20)

        # Password
        self.password_entry = ctk.CTkEntry(
            form_card,
            placeholder_text="Password",
            show="*"
        )
        self.password_entry.pack(pady=10, padx=20)

        # Biometric Selection
        self.biometric_var = ctk.StringVar(value="Face")
        self.biometric_combo = ctk.CTkComboBox(
            form_card,
            values=["Face", "Fingerprint"],
            variable=self.biometric_var,
            state="readonly"
        )
        self.biometric_combo.pack(pady=10, padx=20)

        # Buttons
        btn_frame = ctk.CTkFrame(form_card, fg_color="transparent")
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
            form_card,
            text="Back to Login",
            fg_color="#888888",
            hover_color="#666666",
            command=lambda: controller.show_frame("LoginPage")
        ).pack(pady=10)

    # ---------------------------------------------------------------------
    # ACTION: Register user
    # ---------------------------------------------------------------------
    def handle_register(self):
        name = self.name_entry.get().strip()
        dob = self.dob_entry.get().strip()
        gender = self.gender_var.get()
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        self.biometric_choice = self.biometric_var.get()

        # Basic validations
        if not all([name, dob, gender, email, password]) or gender == "Select Gender":
            messagebox.showerror("Validation", "All fields are required")
            return

        # Validate DOB
        try:
            datetime.strptime(dob, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Validation", "DOB must be in YYYY-MM-DD format")
            return

        # Register
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

        messagebox.showinfo(
            "Registration Successful",
            f"User created successfully.\nAssigned ID: {user_id}\nProceed with biometric capture."
        )

        self.capture_btn.configure(state="normal")

    # ---------------------------------------------------------------------
    # ACTION: Capture biometric data
    # ---------------------------------------------------------------------
    def handle_capture(self):
        if self.current_user_id is None:
            messagebox.showerror("Error", "Please register before capturing biometric data")
            return

        if self.biometric_choice == "Face":
            instructions = [
                "Face the camera, 1 of 5",
                "Face the camera, 1 of 5",
                ", 1 of 5",
                "Smile gently, 4 of 5",
                "Close your eyes, 5 of 5"
            ]

            total_saved = 0
            for step in instructions:
                messagebox.showinfo("Biometric Capture", step)
                saved_count, _ = capture_and_save_face_samples(
                    self.current_user_id,
                    samples=1
                )
                total_saved += saved_count

            if total_saved > 0:
                train_lbph_recognizer()
                self.biometric_captured = True
                messagebox.showinfo("Success", "Facial samples captured successfully")
            else:
                messagebox.showerror("Error", "Failed to capture facial data")
                return

        else:
            response = self.auth.capture_fingerprint_data(self.current_user_id)
            if "captured" in response.lower():
                self.biometric_captured = True
                messagebox.showinfo("Success", "Fingerprint captured successfully")
            else:
                messagebox.showerror("Error", response)
                return

        self.capture_btn.configure(state="disabled")
        messagebox.showinfo("Completed", f"Registration completed for {self.current_user_id}")
