import customtkinter as ctk
from gui.registration_page import RegistrationPage
from gui.login_page import LoginPage
from gui.dashboard import DashboardPage
from app import AuthSystem


class MainApp(ctk.CTk):
    def __init__(self, auth_system: AuthSystem):
        super().__init__()

        # ---------------------------------------------------------
        # Appearance
        # ---------------------------------------------------------
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.title("EHR System")
        self.geometry("1050x650")
        self.minsize(1050, 650)

        # ---------------------------------------------------------
        # App State
        # ---------------------------------------------------------
        self.auth = auth_system
        self.current_user_id = ""
        self.current_user_name = ""
        self.is_admin = False

        # ---------------------------------------------------------
        # Main Container
        # ---------------------------------------------------------
        self.configure(fg_color="#f3f4f6")

        self.outer_frame = ctk.CTkFrame(self, fg_color="#f3f4f6")
        self.outer_frame.pack(fill="both", expand=True)

        self.container = ctk.CTkFrame(
            self.outer_frame,
            fg_color="white",
            corner_radius=20
        )
        self.container.place(relx=0.5, rely=0.5, anchor="center")
        self.container.configure(width=900, height=580)

        # Make fully responsive
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        # ---------------------------------------------------------
        # Load Pages
        # ---------------------------------------------------------
        self.frames = {}
        for F in (RegistrationPage, LoginPage, DashboardPage):
            frame = F(parent=self.container, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # Start at login page
        self.show_frame("LoginPage")

    # ---------------------------------------------------------
    # Frame Switching
    # ---------------------------------------------------------
    def show_frame(self, page_name: str):
        frame = self.frames[page_name]
        frame.tkraise()

        try:
            frame.update()
            self._animate_fade_in(frame)
        except Exception:
            pass

    def _animate_fade_in(self, widget):
        try:
            for _ in range(0, 8):
                widget.update()
                self.update_idletasks()
        except Exception:
            pass

    # ---------------------------------------------------------
    # Successful Login or Post Registration
    # ---------------------------------------------------------
    def on_login_success(self, user_id: str):
        """
        Handles user entry into the dashboard immediately after login
        or auto entry after registration.
        """
        self.current_user_id = user_id
        self.is_admin = user_id.lower() == "admin"

        dashboard: DashboardPage = self.frames["DashboardPage"]

        # ------------------------------
        # Admin Login
        # ------------------------------
        if self.is_admin:
            dashboard.enable_admin_mode()          # Unlock admin functions
            dashboard.load_blockchain_logs()       # Load hashed blockchain events
            self.current_user_name = "Administrator"

        # ------------------------------
        # Normal User Login
        # ------------------------------
        else:
            user_data = self.auth.get_user_profile(user_id)

            if user_data:
                # Display the real name instead of ID
                self.current_user_name = user_data.get("name", user_id)

                # Push user data into dashboard
                dashboard.set_user(user_id)

                # Force reload of freshly edited user details
                dashboard.update_user_view()

            else:
                # Fallback display
                self.current_user_name = user_id

        # Display welcome message
        dashboard.set_welcome_message(self.current_user_name)

        # Show dashboard
        self.show_frame("DashboardPage")


# ---------------------------------------------------------
# Entry Point
# ---------------------------------------------------------
if __name__ == "__main__":
    auth = AuthSystem()
    app = MainApp(auth)
    app.mainloop()
