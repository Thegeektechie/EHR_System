import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from typing import Optional
from app import AuthSystem
from biometric.facial import capture_and_save_face_samples, train_lbph_recognizer


class RegistrationPage(ctk.CTkFrame):
    """Modern Registration page with CustomTkinter and biometric support"""
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.auth: AuthSystem = controller.auth
        self.grid(row=0, column=0, sticky="nsew")
        self.current_user_id: Optional[str] = None
        self.biometric_captured = False
        self.biometric_choice = "Face"

        # Page background
        self.configure(fg_color="#f5f5f5")

        # Title
        ctk.CTkLabel(self, text="Register New User",
                     font=ctk.CTkFont(size=28, weight="bold")).pack(pady=(30, 15))

        # Card container
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
        self.password_entry = ctk.CTkEntry(form_card, placeholder_text="Password", show="*")
        self.password_entry.pack(pady=10, padx=20)

        # Biometric choice
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

        self.register_btn = ctk.CTkButton(btn_frame, text="Register",
                                          width=130, command=self.handle_register)
        self.register_btn.grid(row=0, column=0, padx=10)

        self.capture_btn = ctk.CTkButton(btn_frame, text="Capture Biometric",
                                         width=160, command=self.handle_capture, state="disabled")
        self.capture_btn.grid(row=0, column=1, padx=10)

        # Back to login
        ctk.CTkButton(
            form_card, text="Back to Login", fg_color="#888888",
            hover_color="#666666",
            command=lambda: controller.show_frame("LoginPage")
        ).pack(pady=10)

    def handle_register(self):
        """Register user in AuthSystem and enable biometric capture"""
        name = self.name_entry.get().strip()
        dob = self.dob_entry.get().strip()
        gender = self.gender_var.get()
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        self.biometric_choice = self.biometric_var.get() or "Face"

        if not all([name, dob, gender, email, password]) or gender == "Select Gender":
            messagebox.showerror("Validation", "All fields are required")
            return

        try:
            datetime.strptime(dob, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Validation", "DOB must be YYYY-MM-DD")
            return

        user_id = self.auth.register_user(name, dob, gender, email, password, self.biometric_choice)
        if not user_id:
            messagebox.showerror("Registration Error", "User already exists")
            return

        self.current_user_id = user_id
        self.biometric_captured = False

        messagebox.showinfo(
            "Registration",
            f"User registered successfully.\nUser ID: {user_id}\nNow capture your {self.biometric_choice}"
        )

        self.capture_btn.configure(state="normal")

    def handle_capture(self):
        """Capture facial or fingerprint data for the current user"""
        if self.current_user_id is None:
            messagebox.showerror("Error", "Register first")
            return

        if self.biometric_choice == "Face":
            # five guided instructions
            instructions = [
                "Face the camera",
                "Turn your head slightly to the left",
                "Turn your head slightly to the right",
                "Smile gently",
                "Close your eyes"
            ]

            saved_total = 0

            for step in instructions:
                messagebox.showinfo("Biometric Capture", step)

                saved_count, _ = capture_and_save_face_samples(
                    self.current_user_id,
                    samples=1
                )
                saved_total += saved_count

            if saved_total > 0:
                train_lbph_recognizer()
                messagebox.showinfo("Success", f"{saved_total} face samples captured successfully")
                self.biometric_captured = True
            else:
                messagebox.showerror("Failed", "Face capture failed")

        elif self.biometric_choice == "Fingerprint":
            msg = self.auth.capture_fingerprint_data(self.current_user_id)
            if "captured" in msg.lower():
                messagebox.showinfo("Success", "Fingerprint captured successfully")
                self.biometric_captured = True
            else:
                messagebox.showerror("Failed", msg)

        if self.biometric_captured:
            self.capture_btn.configure(state="disabled")
            messagebox.showinfo("Complete", f"Registration complete for User ID {self.current_user_id}")
