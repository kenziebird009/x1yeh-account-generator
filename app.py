"""
Account Generator -- Main Entry Point
Initializes the application, handles login flow, session restore,
auto-updates, and launches the GUI.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time

import customtkinter as ctk

from api import APIClient
from gui import LoginFrame, MainApp, _get_logo_path
from updater import UpdateChecker, ensure_app_folders
from storage import init_db, seed_default_data
from server import run_server, get_server_port


# ---------------------------------------------------------------------------
# Window Icon Setup
# ---------------------------------------------------------------------------

def _set_window_icon(root) -> None:
    """Set the taskbar/title-bar icon from the logo."""
    logo_path = _get_logo_path()
    if not logo_path:
        return
    try:
        from PIL import Image
        ico_path = os.path.join(_get_app_dir(), "assets", "logo.ico")
        if not os.path.exists(ico_path):
            img = Image.open(logo_path)
            img.save(ico_path, format="ICO", sizes=[(32, 32), (64, 64)])
        root.iconbitmap(default=ico_path)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _get_app_dir() -> str:
    """Return the directory containing the application files."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def load_config() -> dict:
    """Load config.json from the application directory."""
    paths = [
        os.path.join(sys._MEIPASS, "config.json") if getattr(sys, "frozen", False) else "",
        os.path.join(_get_app_dir(), "config.json"),
    ]
    for p in paths:
        if p and os.path.exists(p):
            try:
                with open(p, "r") as fh:
                    return json.load(fh)
            except Exception:
                pass
    return {
        "api_base_url": "https://api.example.com",
        "remember_login": True,
        "theme": "dark",
        "launch_on_startup": False,
        "animations": True,
        "notification_sounds": False,
        "check_for_updates": True,
        "window_width": 1100,
        "window_height": 700,
        "version": "1.0.0",
    }


def save_config(config: dict) -> None:
    """Persist config.json."""
    p = os.path.join(_get_app_dir(), "config.json")
    try:
        with open(p, "w") as fh:
            json.dump(config, fh, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class Application:
    """Orchestrates login -> dashboard flow and handles update checks."""

    def __init__(self):
        self.config = load_config()
        self.api = APIClient(
            base_url=self.config.get("api_base_url", "https://api.example.com")
        )
        self._root: ctk.CTk | None = None
        self._login_frame: LoginFrame | None = None
        self._main_app: MainApp | None = None

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

    # --- launch -------------------------------------------------------------

    def run(self) -> None:
        # Ensure all required folders exist
        ensure_app_folders(_get_app_dir())

        # Initialize database
        init_db()
        seed_default_data()

        # Start local server with health-check polling
        port = run_server()
        if port == 0:
            # Show a simple tkinter error popup since CTk isn't initialized yet
            import tkinter.messagebox as _mb
            _mb.showerror(
                "Server Error",
                "Could not start the local server.\n\n"
                "Possible causes:\n"
                "- Another instance is already running\n"
                "- Port 8099-8108 are all in use\n"
                "- Firewall blocking the connection\n\n"
                "Close any other copies of this app and try again.",
            )
            sys.exit(1)

        self.config["api_base_url"] = f"http://127.0.0.1:{port}"
        self.api.base_url = f"http://127.0.0.1:{port}"

        self._root = ctk.CTk()
        self._root.title("X1YEH Account Generator")
        _set_window_icon(self._root)

        w = self.config.get("window_width", 1100)
        h = self.config.get("window_height", 700)
        self._root.geometry(f"{w}x{h}")
        self._root.minsize(900, 600)
        self._root.configure(fg_color="#080c14")

        self._root.update_idletasks()
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self._root.geometry(f"+{x}+{y}")

        restored = False
        if self.config.get("remember_login", True):
            restored = self.api.restore_session()
            if restored and self._load_and_show_dashboard():
                self._root.mainloop()
                return

        self._show_login()
        self._root.mainloop()

    # --- login flow ---------------------------------------------------------

    def _show_login(self) -> None:
        if self._login_frame:
            self._login_frame.destroy_particles()
            self._login_frame.destroy()
        self._login_frame = LoginFrame(
            self._root,
            on_login=self._on_login_submit,
            on_admin=self._on_admin_submit,
        )
        self._login_frame.pack(fill="both", expand=True)

    def _on_admin_submit(self, admin_key: str) -> None:
        self._login_frame.destroy_particles()
        self._login_frame.destroy()
        self._login_frame = None
        # Login via API with the default admin key so the token is set
        for attempt in range(5):
            result = self.api.login("ADMIN-DEFAULT-KEY")
            if result.get("success", True) and result.get("token"):
                break
            time.sleep(0.4)
        self._load_and_show_dashboard(is_admin=True)

    def _on_login_submit(self, license_key: str) -> None:
        self._login_frame.set_loading(True)
        self.api.login_async(license_key, callback=self._on_login_result)

    def _on_login_result(self, result: dict) -> None:
        if not self._login_frame:
            return

        if result.get("success", True) and result.get("token"):
            self._login_frame.destroy_particles()
            self._login_frame.destroy()
            self._login_frame = None
            self._load_and_show_dashboard()
        else:
            error = result.get("error", "Invalid license key.")
            self._login_frame.on_login_error(error)

    # --- dashboard ----------------------------------------------------------

    def _load_and_show_dashboard(self, is_admin: bool = False) -> bool:
        """Load profile + permissions and show the main app frame. Returns True on success."""
        profile = self.api.get_profile()
        if not profile.get("success", True):
            self._show_login()
            return False

        permissions_resp = self.api.get_permissions()
        permissions = permissions_resp.get("permissions", [])
        if isinstance(permissions, dict):
            permissions = list(permissions.keys())
        if isinstance(permissions, str):
            permissions = [permissions]

        self._main_app = MainApp(
            parent=self._root,
            api_client=self.api,
            config=self.config,
            profile=profile,
            permissions=permissions,
            on_logout=self._on_logout,
            is_admin=is_admin,
        )

        if self.config.get("check_for_updates", True):
            self._check_updates_async()

        return True

    def _on_logout(self) -> None:
        self.config["remember_login"] = False
        save_config(self.config)
        self._main_app = None
        self._show_login()

    # --- updates ------------------------------------------------------------

    def _check_updates_async(self) -> None:
        def _worker() -> None:
            time.sleep(2)
            updater = UpdateChecker(
                current_version=self.config.get("version", "1.0.0"),
                version_info_url=self.config.get(
                    "version_url",
                    f"{self.api.base_url}/version",
                ),
            )
            info = updater.check()
            if info and self._main_app and self._root:
                self._root.after(
                    0,
                    lambda: self._main_app.show_update_dialog(
                        info,
                        on_update=lambda: updater.download_and_install(
                            info,
                            done_callback=lambda ok, err: None,
                        ),
                        on_skip=lambda: None,
                    ),
                )

        t = threading.Thread(target=_worker, daemon=True)
        t.start()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = Application()
    app.run()
