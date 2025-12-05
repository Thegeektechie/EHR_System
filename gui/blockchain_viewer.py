# gui/blockchain_viewer.py
import json
from pathlib import Path
import customtkinter as ctk
from tkinter import ttk, messagebox, StringVar
from utils.helpers import DATA_DIR

LOG_FILE = Path(DATA_DIR) / "blockchain.json"

class BlockchainViewer(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.grid(row=0, column=0, sticky="nsew")
        self.configure(fg_color="#f8fafc")

        # Title
        ctk.CTkLabel(self, text="Blockchain Activity", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(16,6), anchor="w", padx=24)

        # Search bar
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=24, pady=(0,12))
        self.search_var = StringVar()
        search_entry = ctk.CTkEntry(search_frame, placeholder_text="Search by user id, action or file", width=480, textvariable=self.search_var)
        search_entry.pack(side="left", padx=(0,8))
        ctk.CTkButton(search_frame, text="Search", width=100, command=self.refresh_table).pack(side="left")

        # Table container (use classic ttk.Treeview for crisp table UI)
        table_frame = ctk.CTkFrame(self, fg_color="white", corner_radius=12)
        table_frame.pack(fill="both", expand=True, padx=24, pady=(0,24))

        # Create vertical and horizontal scrollbar
        vsb = ttk.Scrollbar(table_frame, orient="vertical")
        hsb = ttk.Scrollbar(table_frame, orient="horizontal")

        columns = ("timestamp", "user_id", "action", "file")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

        # Define headings
        self.tree.heading("timestamp", text="Timestamp")
        self.tree.heading("user_id", text="User ID")
        self.tree.heading("action", text="Action")
        self.tree.heading("file", text="File")

        # column widths
        self.tree.column("timestamp", width=220, anchor="w")
        self.tree.column("user_id", width=120, anchor="center")
        self.tree.column("action", width=160, anchor="w")
        self.tree.column("file", width=200, anchor="w")

        # initial load
        self.refresh_table()

    def load_logs(self):
        """Return a list of events read from blockchain.json"""
        if not LOG_FILE.exists():
            return []
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                # If stored as object with 'events' key
                return data.get("events", []) if isinstance(data, dict) else []
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load blockchain logs: {e}")
            return []

    def refresh_table(self):
        """Reload and display filtered logs"""
        for r in self.tree.get_children():
            self.tree.delete(r)

        logs = self.load_logs()
        q = (self.search_var.get() or "").strip().lower()

        # If not admin, show only logs for the current user
        current_user = None
        if self.controller.frames["DashboardPage"].is_admin:
            current_user = None
        else:
            current_user = self.controller.frames["DashboardPage"].user_id

        # Insert rows
        for ev in sorted(logs, key=lambda x: x.get("timestamp", ""), reverse=True):
            ts = ev.get("timestamp", ev.get("time", ""))
            uid = ev.get("user_id", ev.get("user", ""))
            action = ev.get("action", "")
            file = ev.get("file", ev.get("filename", ""))
            # filter by user if normal user
            if current_user and str(uid) != str(current_user):
                continue
            # simple search
            text = f"{ts} {uid} {action} {file}".lower()
            if q and q not in text:
                continue
            self.tree.insert("", "end", values=(ts, uid, action, file))
