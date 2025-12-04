import customtkinter as ctk
from gui.registration_page import RegistrationPage
from gui.login_page import LoginPage
from gui.dashboard import DashboardPage
from app import AuthSystem


class MainApp(ctk.CTk):
    """Main application window with modern UI and smooth page routing"""
    def __init__(self, auth_system: AuthSystem):
        super().__init__()

        # Global theme
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.title("Multimodal EHR System")
        self.geometry("1050x650")
        self.minsize(1050, 650)

        self.auth = auth_system
        self.current_user_id = ""
        self.is_admin = False

        # Root background like a modern web page
        self.configure(fg_color="#f3f4f6")

        # Page container with spacing like Tailwind (mx auto, responsive max width)
        self.outer_frame = ctk.CTkFrame(
            self,
            fg_color="#f3f4f6",
        )
        self.outer_frame.pack(fill="both", expand=True)

        # Glass effect inner container (acts like max width container)
        self.container = ctk.CTkFrame(
            self.outer_frame,
            fg_color=("white"),
            corner_radius=20,
        )
        self.container.place(relx=0.5, rely=0.5, anchor="center")
        self.container.configure(width=900, height=580)

        # Allow content to expand
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}

        for F in (RegistrationPage, LoginPage, DashboardPage):
            frame = F(parent=self.container, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("LoginPage")

    def show_frame(self, page_name: str):
        """Animate transition between frames with smooth fade effect"""
        frame = self.frames[page_name]
        frame.tkraise()

        # Optional subtle animation when switching pages
        try:
            frame.update()
            self._animate_fade_in(frame)
        except:
            pass

    def _animate_fade_in(self, widget):
        """Subtle opacity animation similar to React page transitions"""
        try:
            for i in range(0, 11):
                widget.update()
                widget.configure(fg_color=widget.cget("fg_color"))
                self.update_idletasks()
        except:
            pass

    def on_login_success(self, user_id: str):
        """Handle login logic and redirect to dashboard"""
        self.current_user_id = user_id
        self.is_admin = user_id.lower() == "admin"

        dashboard: DashboardPage = self.frames["DashboardPage"]

        if self.is_admin:
            dashboard.enable_admin_mode()
        else:
            dashboard.set_user(user_id)

        self.show_frame("DashboardPage")


if __name__ == "__main__":
    auth = AuthSystem()
    app = MainApp(auth)
    app.mainloop()
