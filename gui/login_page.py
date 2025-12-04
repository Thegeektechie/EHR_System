import customtkinter as ctk
from tkinter import messagebox
from app import AuthSystem
from biometric.facial import predict_face


class LoginPage(ctk.CTkFrame):
    """Modern Tailwind-inspired login screen with User and Admin tabs"""
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.auth: AuthSystem = controller.auth

        self.configure(fg_color="#f3f4f6")

        # Title
        title = ctk.CTkLabel(
            self,
            text="Welcome Back",
            font=ctk.CTkFont(size=32, weight="bold")
        )
        title.pack(pady=(40, 10))

        subtitle = ctk.CTkLabel(
            self,
            text="Sign in to continue",
            font=ctk.CTkFont(size=15, weight="normal"),
            text_color="#6b7280"
        )
        subtitle.pack(pady=(0, 20))

        # Main card container
        self.card = ctk.CTkFrame(
            self,
            fg_color="white",
            corner_radius=20
        )
        self.card.pack(pady=10, padx=40, fill="both", ipadx=30, ipady=20)

        # Tabs
        self.tabview = ctk.CTkTabview(
            self.card,
            width=600,
            height=420,
            corner_radius=15,
            fg_color="#ffffff"
        )
        self.tabview.pack(pady=10, padx=20, fill="both")

        self.tabview.add("User Login")
        self.tabview.add("Admin Login")

        # ------------ USER LOGIN TAB ------------
        user_tab = self.tabview.tab("User Login")

        ctk.CTkLabel(
            user_tab,
            text="User Login",
            font=ctk.CTkFont(size=22, weight="bold")
        ).pack(pady=(20, 10))

        self.username_entry = ctk.CTkEntry(
            user_tab,
            placeholder_text="User ID or Email",
            width=300
        )
        self.username_entry.pack(pady=10)

        self.password_entry = ctk.CTkEntry(
            user_tab,
            placeholder_text="Password",
            width=300,
            show="*"
        )
        self.password_entry.pack(pady=10)

        # Login buttons
        user_btn_frame = ctk.CTkFrame(user_tab, fg_color="transparent")
        user_btn_frame.pack(pady=20)

        ctk.CTkButton(
            user_btn_frame,
            text="Login with Password",
            width=240,
            command=self.handle_user_login
        ).grid(row=0, column=0, pady=5)

        ctk.CTkButton(
            user_btn_frame,
            text="Login with Face",
            width=240,
            command=self.handle_face_login
        ).grid(row=1, column=0, pady=5)

        ctk.CTkButton(
            user_btn_frame,
            text="Login with Fingerprint",
            width=240,
            command=self.handle_fingerprint_login
        ).grid(row=2, column=0, pady=5)

        # Account creation
        ctk.CTkButton(
            user_tab,
            text="Create Account",
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            width=200,
            command=lambda: controller.show_frame("RegistrationPage")
        ).pack(pady=15)

        # ------------ ADMIN LOGIN TAB ------------
        admin_tab = self.tabview.tab("Admin Login")

        ctk.CTkLabel(
            admin_tab,
            text="Administrator Login",
            font=ctk.CTkFont(size=22, weight="bold")
        ).pack(pady=(20, 20))

        self.admin_user = ctk.CTkEntry(
            admin_tab,
            placeholder_text="Admin Username",
            width=300
        )
        self.admin_user.pack(pady=10)

        self.admin_pass = ctk.CTkEntry(
            admin_tab,
            placeholder_text="Password",
            width=300,
            show="*"
        )
        self.admin_pass.pack(pady=10)

        ctk.CTkButton(
            admin_tab,
            text="Login as Admin",
            width=240,
            fg_color="#dc2626",
            hover_color="#b91c1c",
            command=self.handle_admin_login
        ).pack(pady=30)

    # ----------------- LOGIN HANDLERS -----------------

    def handle_user_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            messagebox.showwarning("Validation", "Please enter credentials")
            return

        success = self.auth.login_password(username, password)
        if success:
            uid = self.auth.active_session
            display_uid = str(uid).zfill(5) if uid != "Admin" else "Admin"
            self.controller.on_login_success(uid)
            messagebox.showinfo("Login Successful", f"Welcome, User ID {display_uid}")
        else:
            messagebox.showerror("Login Failed", "Invalid credentials")

    def handle_admin_login(self):
        admin_user = self.admin_user.get().strip()
        admin_pass = self.admin_pass.get().strip()

        if admin_user.lower() == "admin" and admin_pass == "Admin@123":
            self.controller.frames["DashboardPage"].enable_admin_mode()
            self.controller.show_frame("DashboardPage")
        else:
            messagebox.showerror("Admin Login Failed", "Incorrect admin credentials")

    def handle_face_login(self):
        user_id, confidence = predict_face()
        if user_id:
            self.auth.active_session = user_id
            display_uid = str(user_id).zfill(5)
            self.controller.on_login_success(user_id)
            messagebox.showinfo("Face Login Successful", f"Welcome, User ID {display_uid}")
        else:
            messagebox.showerror("Face Login Failed", "Face not recognized")

    def handle_fingerprint_login(self):
        user_id, msg = self.auth.login_fingerprint()
        if user_id:
            display_uid = str(user_id).zfill(5)
            self.controller.on_login_success(user_id)
            messagebox.showinfo("Fingerprint Login Successful", f"Welcome, User ID {display_uid}")
        else:
            messagebox.showerror("Fingerprint Login Failed", msg)
