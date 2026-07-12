"""
GUI Module
Premium dark-themed UI built with CustomTkinter.
Includes particle background, login panel, dashboard with sidebar,
account generator, stock view, settings, and about page.
"""

from __future__ import annotations

import json
import os
import sys
import random
import math
import threading
import time
from typing import Any, Callable, Optional

import tkinter
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# --- Constants ---------------------------------------------------------------
APP_TITLE = "X1YEH Account Generator"
MIN_WIDTH = 900
MIN_HEIGHT = 600

# Color scheme
COLORS = {
    "bg_primary": "#080c14",
    "bg_secondary": "#111827",
    "bg_card": "#161e2e",
    "bg_input": "#0a0f1a",
    "bg_sidebar": "#0b101c",
    "accent": "#3b82f6",
    "accent_hover": "#2563eb",
    "accent_light": "#60a5fa",
    "text_primary": "#e6edf3",
    "text_secondary": "#8b949e",
    "text_muted": "#6e7681",
    "success": "#22c55e",
    "danger": "#ef4444",
    "warning": "#f59e0b",
    "border": "#30363d",
    "glass": "#1e2533",
    "sidebar_hover": "#1c2333",
    "sidebar_active": "#1a3350",
    "card_border": "#2a3140",
}

FONTS: dict[str, tuple[str, int]] = {
    "heading": ("Segoe UI", 24),
    "subheading": ("Segoe UI", 16),
    "body": ("Segoe UI", 13),
    "small": ("Segoe UI", 11),
    "mono": ("Consolas", 12),
    "button": ("Segoe UI", 14),
    "sidebar": ("Segoe UI", 14),
}

# ---------------------------------------------------------------------------
# Logo Loading
# ---------------------------------------------------------------------------

def _get_logo_path() -> str | None:
    """Find the logo file in assets/ or alongside the exe."""
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(sys._MEIPASS, "assets", "logo.png"))
        candidates.append(os.path.join(sys._MEIPASS, "logo.png"))
    base = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(base, "assets", "logo.png"))
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def load_logo(size: tuple[int, int] = (48, 48)) -> ctk.CTkImage | None:
    """Load and resize the logo for use in CTk widgets."""
    path = _get_logo_path()
    if not path:
        return None
    try:
        img = Image.open(path).convert("RGBA")
        img = img.resize(size, Image.LANCZOS)
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    except Exception:
        return None


def load_logo_as_icon(size: tuple[int, int] = (32, 32)) -> ctk.CTkImage | None:
    return load_logo(size)


# ---------------------------------------------------------------------------
# Particle Background
# ---------------------------------------------------------------------------
# Particle Background
# ---------------------------------------------------------------------------

class Particle:
    """Single animated particle."""

    __slots__ = ("x", "y", "radius", "speed", "alpha", "color", "vx", "vy")

    def __init__(self, w: int, h: int):
        self.x = random.uniform(0, w)
        self.y = random.uniform(0, h)
        self.radius = random.uniform(0.5, 2.5)
        self.speed = random.uniform(0.3, 1.2)
        self.alpha = random.uniform(20, 80)
        self.color = "#3b82f6"
        self.vx = random.uniform(-0.3, 0.3)
        self.vy = random.uniform(-0.3, 0.3)

    def update(self, w: int, h: int):
        self.x += self.vx
        self.y -= self.speed  # float upward
        # Wrap around
        if self.y < -10:
            self.y = h + 10
            self.x = random.uniform(0, w)
        if self.x < -10:
            self.x = w + 10
        elif self.x > w + 10:
            self.x = -10
        # Occasional random nudge
        if random.random() < 0.01:
            self.vx += random.uniform(-0.1, 0.1)
            self.alpha = min(100, max(10, self.alpha + random.uniform(-5, 5)))


class ParticleBackground(ctk.CTkCanvas):
    """Canvas that renders an animated particle field."""

    def __init__(self, parent: ctk.CTkFrame, particle_count: int = 80):
        super().__init__(parent, highlightthickness=0, bg=COLORS["bg_primary"])
        self._particles = [Particle(1100, 700) for _ in range(particle_count)]
        self._running = True
        self._bind_id: Optional[str] = None

    def start(self):
        self._running = True
        self._animate()

    def stop(self):
        self._running = False
        if self._bind_id:
            self.after_cancel(self._bind_id)

    def _animate(self):
        if not self._running:
            return
        w = self.winfo_width()
        h = self.winfo_height()
        self.delete("all")
        for p in self._particles:
            p.update(w, h)
            # Draw as small filled circle
            alpha_hex = format(int(p.alpha), "02x")
            fill = f"#{alpha_hex}{alpha_hex}{alpha_hex}"  # white-ish with low alpha
            x, y, r = p.x, p.y, p.radius
            self.create_oval(
                x - r, y - r, x + r, y + r,
                fill=fill, outline="", tags="particle"
            )
        self._bind_id = self.after(33, self._animate)


# ---------------------------------------------------------------------------
# Base Glass Card
# ---------------------------------------------------------------------------

class GlassCard(ctk.CTkFrame):
    """A card with a glass-like semi-transparent border."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["card_border"],
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Toast / Notification
# ---------------------------------------------------------------------------

class Toast:
    """Floating notification that appears and fades."""

    @staticmethod
    def show(
        parent,
        message: str,
        kind: str = "info",
        duration_ms: int = 3000,
    ):
        colors_map = {
            "info": COLORS["accent"],
            "success": COLORS["success"],
            "error": COLORS["danger"],
            "warning": COLORS["warning"],
        }
        color = colors_map.get(kind, COLORS["accent"])
        frame = ctk.CTkFrame(
            parent,
            fg_color=color,
            corner_radius=8,
        )
        label = ctk.CTkLabel(
            frame,
            text=message,
            font=ctk.CTkFont(*FONTS["body"]),
            text_color="#ffffff",
            padx=20,
            pady=10,
        )
        label.pack()
        # Place at top-center
        def _place():
            pw = parent.winfo_width()
            frame.update_idletasks()
            fw = frame.winfo_reqwidth()
            x = (pw - fw) // 2
            frame.place(x=x, y=20)
        parent.after(50, _place)

        def _destroy():
            frame.place_forget()
            frame.destroy()
        parent.after(duration_ms, _destroy)


# ---------------------------------------------------------------------------
# Login Frame
# ---------------------------------------------------------------------------

class AdminKeyDialog(ctk.CTkToplevel):
    """Modal dialog for admin key entry."""

    def __init__(self, parent, on_submit: Callable[[str], None]):
        super().__init__(parent)
        self.title("Admin Access")
        self.geometry("360x220")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg_secondary"])
        self.transient(parent)
        self.grab_set()
        self.on_submit = on_submit

        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        x = px + (pw - 360) // 2
        y = py + (ph - 220) // 2
        self.geometry(f"+{x}+{y}")

        self._build()

    def _build(self):
        ctk.CTkLabel(
            self,
            text="Admin Access",
            font=ctk.CTkFont(*FONTS["subheading"]),
            text_color=COLORS["text_primary"],
        ).pack(pady=(25, 5))

        ctk.CTkLabel(
            self,
            text="Enter the admin key to continue",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_secondary"],
        ).pack(pady=(0, 15))

        self.key_var = tkinter.StringVar()
        entry = ctk.CTkEntry(
            self,
            textvariable=self.key_var,
            placeholder_text="Admin Key",
            width=260,
            height=38,
            font=ctk.CTkFont(*FONTS["mono"]),
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            corner_radius=8,
            justify="center",
            show="*",
        )
        entry.pack(pady=(0, 5))
        entry.bind("<Return>", lambda _e: self._submit())

        self.error_lbl = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["danger"],
        )
        self.error_lbl.pack()

        ctk.CTkButton(
            self,
            text="Submit",
            command=self._submit,
            width=260,
            height=36,
            font=ctk.CTkFont(*FONTS["body"]),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=8,
        ).pack(pady=(10, 0))

    def _submit(self):
        key = self.key_var.get().strip()
        if not key:
            self.error_lbl.configure(text="Please enter an admin key.")
            return
        if key != "8524567475":
            self.error_lbl.configure(text="Invalid admin key.")
            return
        self.destroy()
        self.on_submit(key)


class AdminFrame(ctk.CTkFrame):
    """Full admin panel: Dashboard, Keys, Stock, Logs."""

    SERVER_URL = "http://127.0.0.1:8099"

    def __init__(self, parent, api_client):
        super().__init__(parent, fg_color="transparent")
        self.api = api_client
        self._sub_page = "dashboard"
        self._build()

    def _api(self, method: str, path: str, json_data=None, callback=None):
        """Async API call to the local server."""
        import requests as _r
        def _w():
            try:
                url = f"{self.SERVER_URL}{path}"
                if method == "GET":
                    r = _r.get(url, timeout=10, params=json_data)
                elif method == "POST":
                    r = _r.post(url, json=json_data, timeout=10)
                elif method == "DELETE":
                    r = _r.delete(url, timeout=10)
                elif method == "PUT":
                    r = _r.put(url, json=json_data, timeout=10)
                else:
                    r = _r.get(url, timeout=10)
                data = r.json()
                self.after(0, lambda: callback(data))
            except Exception as e:
                self.after(0, lambda: callback({"success": False, "error": str(e)}))
        threading.Thread(target=_w, daemon=True).start()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self):
        ctk.CTkLabel(self, text="Admin Panel", font=ctk.CTkFont(*FONTS["heading"]),
                     text_color=COLORS["text_primary"]).pack(anchor="w", pady=(10, 10))

        # Tab bar
        tab_frame = ctk.CTkFrame(self, fg_color="transparent")
        tab_frame.pack(fill="x")
        self._tabs = {}
        for tab_id, label in [("dashboard", "Dashboard"), ("keys", "Keys"),
                               ("stock", "Stock"), ("logs", "Logs")]:
            btn = ctk.CTkButton(
                tab_frame, text=label, width=90, height=30,
                font=ctk.CTkFont(*FONTS["small"]),
                fg_color=COLORS["bg_card"], hover_color=COLORS["sidebar_hover"],
                text_color=COLORS["text_secondary"],
                command=lambda t=tab_id: self._show_sub_page(t),
            )
            btn.pack(side="left", padx=(0, 4))
            self._tabs[tab_id] = btn

        ctk.CTkFrame(self, height=1, fg_color=COLORS["border"]).pack(fill="x", pady=(8, 10))

        # Content container
        self._sub_content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._sub_content.pack(fill="both", expand=True)

        self._show_sub_page("dashboard")

    def _show_sub_page(self, page_id: str):
        self._sub_page = page_id
        for pid, btn in self._tabs.items():
            if pid == page_id:
                btn.configure(fg_color=COLORS["accent"], text_color="#fff")
            else:
                btn.configure(fg_color=COLORS["bg_card"], text_color=COLORS["text_secondary"])

        for w in self._sub_content.winfo_children():
            w.destroy()

        if page_id == "dashboard":
            self._build_dashboard()
        elif page_id == "keys":
            self._build_keys()
        elif page_id == "stock":
            self._build_stock()
        elif page_id == "logs":
            self._build_logs()

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def _build_dashboard(self):
        self._api("GET", "/admin/stats", callback=self._render_dashboard)

    def _render_dashboard(self, data):
        ctk.CTkLabel(self._sub_content, text="Dashboard", font=ctk.CTkFont(*FONTS["subheading"]),
                     text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, 8))
        if not data.get("success"):
            ctk.CTkLabel(self._sub_content, text="Failed to load stats.",
                         font=ctk.CTkFont(*FONTS["small"]), text_color=COLORS["danger"]).pack()
            return

        licenses = data.get("licenses", {})
        stock = data.get("stock", {})
        gen = data.get("generations", {})

        cards = [
            ("Total Licenses", licenses.get("total", 0)),
            ("Active Keys", licenses.get("active", 0)),
            ("Disabled Keys", licenses.get("disabled", 0)),
            ("Total Stock", stock.get("total", 0)),
            ("Available Stock", stock.get("available", 0)),
            ("Used Stock", stock.get("used", 0)),
            ("Generated Today", gen.get("today", 0)),
            ("Total Generated", gen.get("total", 0)),
        ]

        row_frame = None
        for i, (label, value) in enumerate(cards):
            if i % 3 == 0:
                row_frame = ctk.CTkFrame(self._sub_content, fg_color="transparent")
                row_frame.pack(fill="x", pady=2)
            card = GlassCard(row_frame)
            card.pack(side="left", padx=4, fill="x", expand=True)
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(*FONTS["small"]),
                         text_color=COLORS["text_muted"]).pack(padx=12, pady=(8, 0))
            ctk.CTkLabel(card, text=str(value), font=ctk.CTkFont(size=26, weight="bold"),
                         text_color=COLORS["accent"]).pack(padx=12, pady=(0, 8))

    # ------------------------------------------------------------------
    # Keys
    # ------------------------------------------------------------------

    def _build_keys(self):
        # Create key form
        card = GlassCard(self._sub_content)
        card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(card, text="Create License Key", font=ctk.CTkFont(*FONTS["subheading"]),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=14, pady=(10, 6))

        f1 = ctk.CTkFrame(card, fg_color="transparent")
        f1.pack(fill="x", padx=14, pady=4)

        ctk.CTkLabel(f1, text="Username", font=ctk.CTkFont(*FONTS["small"]),
                     text_color=COLORS["text_muted"]).grid(row=0, column=0, sticky="w", padx=2)
        self._key_user = ctk.CTkEntry(f1, width=130, height=30, font=ctk.CTkFont(*FONTS["small"]),
                                       fg_color=COLORS["bg_input"], border_color=COLORS["border"])
        self._key_user.grid(row=0, column=1, padx=2)

        ctk.CTkLabel(f1, text="Daily Limit", font=ctk.CTkFont(*FONTS["small"]),
                     text_color=COLORS["text_muted"]).grid(row=0, column=2, sticky="w", padx=(10, 2))
        self._key_limit = ctk.CTkEntry(f1, width=50, height=30, font=ctk.CTkFont(*FONTS["small"]),
                                        fg_color=COLORS["bg_input"], border_color=COLORS["border"])
        self._key_limit.insert(0, "5")
        self._key_limit.grid(row=0, column=3, padx=2)

        ctk.CTkLabel(f1, text="Max Uses", font=ctk.CTkFont(*FONTS["small"]),
                     text_color=COLORS["text_muted"]).grid(row=0, column=4, sticky="w", padx=(10, 2))
        self._key_maxuses = ctk.CTkEntry(f1, width=50, height=30, font=ctk.CTkFont(*FONTS["small"]),
                                          fg_color=COLORS["bg_input"], border_color=COLORS["border"])
        self._key_maxuses.grid(row=0, column=5, padx=2)

        ctk.CTkLabel(f1, text="Expiry", font=ctk.CTkFont(*FONTS["small"]),
                     text_color=COLORS["text_muted"]).grid(row=0, column=6, sticky="w", padx=(10, 2))
        self._key_expiry = ctk.CTkOptionMenu(
            f1, values=["30 days", "7 days", "1 day", "90 days", "Lifetime", "Custom"],
            font=ctk.CTkFont(*FONTS["small"]), fg_color=COLORS["bg_input"],
            button_color=COLORS["accent"], button_hover_color=COLORS["accent_hover"],
            width=110, height=30,
        )
        self._key_expiry.set("30 days")
        self._key_expiry.grid(row=0, column=7, padx=2)

        self._key_custom_date = ctk.CTkEntry(f1, width=110, height=30, font=ctk.CTkFont(*FONTS["small"]),
                                              fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                                              placeholder_text="YYYY-MM-DD")

        ctk.CTkButton(f1, text="Create", command=self._do_create_key, width=70, height=30,
                      font=ctk.CTkFont(*FONTS["small"]), fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_hover"],
                      corner_radius=6).grid(row=0, column=8, padx=(10, 0))

        # Permissions checkboxes
        ctk.CTkLabel(card, text="Permissions", font=ctk.CTkFont(*FONTS["small"]),
                     text_color=COLORS["text_muted"]).pack(anchor="w", padx=14, pady=(8, 2))
        cb_frame = ctk.CTkFrame(card, fg_color="transparent")
        cb_frame.pack(fill="x", padx=14, pady=(0, 8))

        self._perm_vars: dict[str, tkinter.BooleanVar] = {}
        from storage import ALL_GENERATORS
        for idx, cat in enumerate(ALL_GENERATORS):
            var = tkinter.BooleanVar(value=True)
            cb = ctk.CTkCheckBox(cb_frame, text=cat, variable=var,
                                  font=ctk.CTkFont(*FONTS["small"]),
                                  fg_color=COLORS["accent"], border_color=COLORS["border"],
                                  text_color=COLORS["text_secondary"],
                                  checkbox_width=16, checkbox_height=16)
            cb.grid(row=idx // 4, column=idx % 4, sticky="w", padx=6, pady=2)
            self._perm_vars[cat] = var

        self._key_status = ctk.CTkLabel(card, text="", font=ctk.CTkFont(*FONTS["small"]))
        self._key_status.pack(anchor="w", padx=14, pady=(0, 6))

        # License list
        card2 = GlassCard(self._sub_content)
        card2.pack(fill="x")
        ctk.CTkLabel(card2, text="Existing Keys", font=ctk.CTkFont(*FONTS["subheading"]),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=14, pady=(10, 6))
        self._key_list_frame = ctk.CTkFrame(card2, fg_color="transparent")
        self._key_list_frame.pack(fill="x", padx=14, pady=(0, 10))

        self._api("GET", "/admin/licenses", callback=self._render_keys)

    def _render_keys(self, data):
        frame = self._key_list_frame
        for w in frame.winfo_children():
            w.destroy()
        licenses = data.get("licenses", [])
        if not licenses:
            ctk.CTkLabel(frame, text="No keys found.", font=ctk.CTkFont(*FONTS["small"]),
                         text_color=COLORS["text_muted"]).pack()
            return
        for lic in licenses:
            row = ctk.CTkFrame(frame, fg_color=COLORS["bg_card"], corner_radius=6)
            row.pack(fill="x", pady=2, ipady=2)

            key_str = lic["license_key"]
            perms = ", ".join(lic.get("permissions", [])) or "None"
            status_color = COLORS["success"] if lic["status"] == "active" else ("#f59e0b" if lic["status"] == "expired" else COLORS["danger"])
            info = f"{key_str[:22]}...  |  {lic['username']}"
            ctk.CTkLabel(row, text=info, font=ctk.CTkFont("Consolas", 10),
                         text_color=COLORS["text_secondary"], anchor="w").pack(side="left", padx=8)

            status_lbl = ctk.CTkLabel(row, text=lic["status"].upper(), font=ctk.CTkFont("Segoe UI", 9, "bold"),
                                       text_color=status_color, width=60)
            status_lbl.pack(side="left", padx=4)

            exp = lic.get("expiry_date") or "Never"
            ctk.CTkLabel(row, text=f"Exp: {exp}", font=ctk.CTkFont(*FONTS["small"]),
                         text_color=COLORS["text_muted"], width=100).pack(side="left")

            ctk.CTkButton(row, text="Copy", width=45, height=22, font=ctk.CTkFont("Segoe UI", 9),
                          fg_color=COLORS["bg_card"], hover_color=COLORS["sidebar_hover"],
                          command=lambda k=key_str: self._copy_text(k),
                          corner_radius=4).pack(side="right", padx=2)
            ctk.CTkButton(row, text="Toggle", width=50, height=22, font=ctk.CTkFont("Segoe UI", 9),
                          fg_color=("#22c55e" if lic["status"] == "active" else COLORS["accent"]),
                          hover_color=("#16a34a" if lic["status"] == "active" else COLORS["accent_hover"]),
                          command=lambda lid=lic["id"]: self._toggle_key(lid),
                          corner_radius=4).pack(side="right", padx=2)
            ctk.CTkButton(row, text="Del", width=40, height=22, font=ctk.CTkFont("Segoe UI", 9),
                          fg_color=COLORS["danger"], hover_color="#dc2626",
                          command=lambda lid=lic["id"]: self._delete_key(lid),
                          corner_radius=4).pack(side="right", padx=2)

    def _do_create_key(self):
        username = self._key_user.get().strip() or "User"
        try:
            daily_limit = int(self._key_limit.get().strip())
        except ValueError:
            daily_limit = 5
        try:
            max_uses_raw = self._key_maxuses.get().strip()
            max_uses = int(max_uses_raw) if max_uses_raw else None
        except ValueError:
            max_uses = None

        expiry = self._key_expiry.get()
        expiry_map = {"1 day": 1, "7 days": 7, "30 days": 30, "90 days": 90, "Lifetime": "lifetime", "Custom": "custom"}
        expiry_days = expiry_map.get(expiry, 30)
        custom_expiry = None
        if expiry_days == "custom":
            custom_expiry = self._key_custom_date.get().strip() or None

        permissions = [cat for cat, var in self._perm_vars.items() if var.get()]

        def _cb(resp):
            if resp.get("success"):
                k = resp.get("license_key", "")
                self._key_status.configure(text=f"Created: {k}", text_color=COLORS["success"])
                self._copy_text(k)
                self._api("GET", "/admin/licenses", callback=self._render_keys)
            else:
                self._key_status.configure(text=resp.get("error", "Failed"), text_color=COLORS["danger"])

        self._api("POST", "/admin/licenses",
                   json={"username": username, "permissions": permissions, "daily_limit": daily_limit,
                         "max_uses": max_uses, "expiry": expiry_days, "custom_expiry": custom_expiry},
                   callback=_cb)

    def _toggle_key(self, lic_id: int):
        def _cb(resp):
            if resp.get("success"):
                self._api("GET", "/admin/licenses", callback=self._render_keys)
        self._api("POST", f"/admin/licenses/{lic_id}/toggle", callback=_cb)

    def _delete_key(self, lic_id: int):
        def _cb(resp):
            if resp.get("success"):
                self._api("GET", "/admin/licenses", callback=self._render_keys)
        self._api("DELETE", f"/admin/licenses/{lic_id}", callback=_cb)

    def _copy_text(self, text: str):
        top = self.winfo_toplevel()
        top.clipboard_clear()
        top.clipboard_append(text)
        Toast.show(top, "Copied!", "success")

    # ------------------------------------------------------------------
    # Stock
    # ------------------------------------------------------------------

    def _build_stock(self):
        card = GlassCard(self._sub_content)
        card.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(card, text="Stock Management", font=ctk.CTkFont(*FONTS["subheading"]),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=14, pady=(10, 6))

        # Bulk paste
        ctk.CTkLabel(card, text="Bulk Import (email:password, one per line)", font=ctk.CTkFont(*FONTS["small"]),
                     text_color=COLORS["text_muted"]).pack(anchor="w", padx=14)
        self._stock_text = ctk.CTkTextbox(card, height=100, font=ctk.CTkFont("Consolas", 11),
                                           fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                                           border_width=1, corner_radius=6, wrap="none")
        self._stock_text.pack(fill="x", padx=14, pady=(2, 8))

        f1 = ctk.CTkFrame(card, fg_color="transparent")
        f1.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(f1, text="Category", font=ctk.CTkFont(*FONTS["small"]),
                     text_color=COLORS["text_muted"]).pack(side="left")
        self._stock_cat = ctk.CTkEntry(f1, width=130, height=30, font=ctk.CTkFont(*FONTS["small"]),
                                        fg_color=COLORS["bg_input"], border_color=COLORS["border"])
        self._stock_cat.pack(side="left", padx=6)

        ctk.CTkButton(f1, text="Import", command=self._do_bulk_import, width=70, height=30,
                      font=ctk.CTkFont(*FONTS["small"]), fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_hover"], corner_radius=6).pack(side="left", padx=4)
        ctk.CTkButton(f1, text="Dedup", command=self._do_dedup, width=60, height=30,
                      font=ctk.CTkFont(*FONTS["small"]), fg_color=COLORS["bg_card"],
                      hover_color=COLORS["sidebar_hover"], corner_radius=6).pack(side="left", padx=4)
        ctk.CTkButton(f1, text="Del Used", command=self._do_del_used, width=70, height=30,
                      font=ctk.CTkFont(*FONTS["small"]), fg_color=COLORS["danger"],
                      hover_color="#dc2626", corner_radius=6).pack(side="right", padx=2)
        ctk.CTkButton(f1, text="Export", command=self._do_export, width=60, height=30,
                      font=ctk.CTkFont(*FONTS["small"]), fg_color=COLORS["bg_card"],
                      hover_color=COLORS["sidebar_hover"], corner_radius=6).pack(side="right", padx=2)
        ctk.CTkButton(f1, text="Clear", command=self._do_clear_stock, width=55, height=30,
                      font=ctk.CTkFont(*FONTS["small"]), fg_color="#b91c1c",
                      hover_color="#7f1d1d", corner_radius=6).pack(side="right", padx=2)

        self._stock_status = ctk.CTkLabel(card, text="", font=ctk.CTkFont(*FONTS["small"]))
        self._stock_status.pack(anchor="w", padx=14, pady=(4, 8))

        # Stock list
        ctk.CTkLabel(self._sub_content, text="Current Stock", font=ctk.CTkFont(*FONTS["subheading"]),
                     text_color=COLORS["text_primary"]).pack(anchor="w", pady=(8, 4))

        f_search = ctk.CTkFrame(self._sub_content, fg_color="transparent")
        f_search.pack(fill="x")
        self._stock_search = ctk.CTkEntry(f_search, width=200, height=28, font=ctk.CTkFont(*FONTS["small"]),
                                           fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                                           placeholder_text="Search email...")
        self._stock_search.pack(side="left")
        ctk.CTkButton(f_search, text="Search", command=self._refresh_stock, width=60, height=28,
                      font=ctk.CTkFont(*FONTS["small"]), fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_hover"], corner_radius=6).pack(side="left", padx=4)

        self._stock_list = ctk.CTkScrollableFrame(self._sub_content, fg_color="transparent", height=250)
        self._stock_list.pack(fill="x", pady=(6, 0))

        self._refresh_stock()

    def _refresh_stock(self):
        q = self._stock_search.get().strip() if hasattr(self, '_stock_search') else ""
        self._api("GET", "/admin/stock", {"search": q}, callback=self._render_stock)

    def _render_stock(self, data):
        frame = self._stock_list
        for w in frame.winfo_children():
            w.destroy()

        accounts = data.get("accounts", [])
        summary = data.get("summary", {})
        cats = summary.get("categories", {})

        # Summary bar
        summary_row = ctk.CTkFrame(frame, fg_color="transparent")
        summary_row.pack(fill="x", pady=(0, 6))
        for cat_name, cat_info in cats.items():
            lbl = ctk.CTkLabel(
                summary_row,
                text=f"{cat_name}: {cat_info['remaining']}/{cat_info['total']}",
                font=ctk.CTkFont(*FONTS["small"]),
                text_color=COLORS["accent"],
            )
            lbl.pack(side="left", padx=6)

        if not accounts:
            ctk.CTkLabel(frame, text="No stock found.", font=ctk.CTkFont(*FONTS["small"]),
                         text_color=COLORS["text_muted"]).pack(pady=8)
            return

        ctk.CTkLabel(frame, text=f"{len(accounts)} accounts shown", font=ctk.CTkFont(*FONTS["small"]),
                     text_color=COLORS["text_muted"]).pack(anchor="w", pady=(0, 4))

        for acc in accounts[:100]:
            row = ctk.CTkFrame(frame, fg_color=COLORS["bg_card"], corner_radius=4)
            row.pack(fill="x", pady=1, ipady=1)
            used_marker = " *USED*" if acc["used"] else ""
            ctk.CTkLabel(row, text=f"[{acc['category']}]{used_marker} {acc['email']}:{acc['password']}",
                         font=ctk.CTkFont("Consolas", 10), text_color=COLORS["text_secondary"],
                         anchor="w").pack(side="left", padx=6)
            ctk.CTkButton(row, text="X", width=24, height=18, font=ctk.CTkFont("Segoe UI", 8),
                          fg_color=COLORS["danger"], hover_color="#dc2626",
                          command=lambda aid=acc["id"]: self._del_single_stock(aid),
                          corner_radius=3).pack(side="right", padx=4)

    def _do_bulk_import(self):
        cat = self._stock_cat.get().strip()
        lines = self._stock_text.get("1.0", "end-1c").strip()
        if not cat or not lines:
            self._stock_status.configure(text="Category and accounts required.", text_color=COLORS["danger"])
            return
        def _cb(resp):
            if resp.get("success"):
                self._stock_status.configure(
                    text=f"Added {resp['added']}, dup {resp.get('duplicates', 0)}",
                    text_color=COLORS["success"])
                self._stock_text.delete("1.0", "end")
                self._refresh_stock()
            else:
                self._stock_status.configure(text=resp.get("error", "Failed"), text_color=COLORS["danger"])
        self._api("POST", "/admin/stock/bulk", {"category": cat, "lines": lines}, callback=_cb)

    def _del_single_stock(self, aid: int):
        def _cb(resp):
            if resp.get("success"):
                self._refresh_stock()
        self._api("DELETE", f"/admin/stock/{aid}", callback=_cb)

    def _do_dedup(self):
        def _cb(resp):
            self._stock_status.configure(text=f"Duplicates removed: {resp.get('removed', 0)}",
                                          text_color=COLORS["success"])
            self._refresh_stock()
        self._api("POST", "/admin/stock/dedup", callback=_cb)

    def _do_del_used(self):
        def _cb(resp):
            self._stock_status.configure(text=f"Used deleted: {resp.get('deleted', 0)}",
                                          text_color=COLORS["success"])
            self._refresh_stock()
        self._api("POST", "/admin/stock/delete-used", callback=_cb)

    def _do_export(self):
        def _cb(resp):
            data = resp.get("data", "")
            if data:
                self._stock_text.delete("1.0", "end")
                self._stock_text.insert("1.0", data)
                self._stock_status.configure(text="Exported to paste area.", text_color=COLORS["success"])
        self._api("GET", "/admin/stock/export", callback=_cb)

    def _do_clear_stock(self):
        def _cb(resp):
            self._stock_status.configure(text=f"Cleared {resp.get('deleted', 0)} accounts.",
                                          text_color=COLORS["success"])
            self._refresh_stock()
        self._api("POST", "/admin/stock/clear", callback=_cb)

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    def _build_logs(self):
        ctk.CTkLabel(self._sub_content, text="Activity Logs", font=ctk.CTkFont(*FONTS["subheading"]),
                     text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, 6))

        ctk.CTkLabel(self._sub_content, text="Admin Logs", font=ctk.CTkFont(*FONTS["body"]),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(4, 2))
        self._admin_logs_frame = ctk.CTkFrame(self._sub_content, fg_color="transparent")
        self._admin_logs_frame.pack(fill="x")

        ctk.CTkLabel(self._sub_content, text="Generation Logs", font=ctk.CTkFont(*FONTS["body"]),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(10, 2))
        self._gen_logs_frame = ctk.CTkFrame(self._sub_content, fg_color="transparent")
        self._gen_logs_frame.pack(fill="x")

        self._api("GET", "/admin/logs", callback=self._render_logs_page)

    def _render_logs_page(self, data):
        for f in (self._admin_logs_frame, self._gen_logs_frame):
            for w in f.winfo_children():
                w.destroy()

        admin_logs = data.get("admin_logs", [])
        gen_logs = data.get("gen_logs", [])

        if not admin_logs:
            ctk.CTkLabel(self._admin_logs_frame, text="No admin activity.",
                         font=ctk.CTkFont(*FONTS["small"]), text_color=COLORS["text_muted"]).pack()
        for log in admin_logs[:20]:
            txt = f"{log['created_at']}  {log['action']}  {log.get('detail', '')}"
            ctk.CTkLabel(self._admin_logs_frame, text=txt, font=ctk.CTkFont("Consolas", 10),
                         text_color=COLORS["text_muted"], anchor="w").pack(fill="x")

        if not gen_logs:
            ctk.CTkLabel(self._gen_logs_frame, text="No generations yet.",
                         font=ctk.CTkFont(*FONTS["small"]), text_color=COLORS["text_muted"]).pack()
        for log in gen_logs[:30]:
            uname = log.get("username", "")
            txt = f"{log['created_at']}  {log['license_key'][:10]}...  {log['category']}  {log.get('email', '')}"
            if uname:
                txt += f"  [{uname}]"
            color = COLORS["success"] if log["success"] else COLORS["danger"]
            ctk.CTkLabel(self._gen_logs_frame, text=txt, font=ctk.CTkFont("Consolas", 10),
                         text_color=color, anchor="w").pack(fill="x")


class LoginFrame(ctk.CTkFrame):
    """License key login screen with particle background and glass panel."""

    def __init__(self, parent, on_login: Callable[[str], None], on_admin: Callable[[str], None] | None = None):
        super().__init__(parent, fg_color="transparent")
        self.on_login = on_login
        self.on_admin = on_admin
        self._build_ui()

    def _build_ui(self):
        # Particle canvas fills entire area
        self.particles = ParticleBackground(self, particle_count=100)
        self.particles.pack(fill="both", expand=True)

        # Center login panel
        panel = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_secondary"],
            corner_radius=16,
            border_width=1,
            border_color=COLORS["border"],
            width=420,
            height=520,
        )
        panel.place(relx=0.5, rely=0.5, anchor="center")
        panel.pack_propagate(False)

        # Accent top bar
        accent_bar = ctk.CTkFrame(
            panel, height=3,
            fg_color=COLORS["accent"],
            corner_radius=0,
        )
        accent_bar.pack(fill="x")

        # Logo
        logo_img = load_logo((64, 64))
        if logo_img:
            logo_label = ctk.CTkLabel(panel, image=logo_img, text="")
            logo_label.pack(pady=(35, 5))
        else:
            logo_label = ctk.CTkLabel(
                panel,
                text=APP_TITLE,
                font=ctk.CTkFont("Segoe UI", 22, "bold"),
                text_color=COLORS["accent"],
            )
            logo_label.pack(pady=(40, 5))

        title = ctk.CTkLabel(
            panel,
            text=APP_TITLE,
            font=ctk.CTkFont(*FONTS["heading"]),
            text_color=COLORS["text_primary"],
        )
        title.pack()

        subtitle = ctk.CTkLabel(
            panel,
            text="Enter your license key to continue",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_secondary"],
        )
        subtitle.pack(pady=(5, 30))

        # License key entry
        self.entry_var = tkinter.StringVar()
        self.entry = ctk.CTkEntry(
            panel,
            textvariable=self.entry_var,
            placeholder_text="XXXXX-XXXXX-XXXXX-XXXXX-XXXXX",
            width=300,
            height=44,
            font=ctk.CTkFont(*FONTS["mono"]),
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            border_width=2,
            corner_radius=10,
            justify="center",
        )
        self.entry.pack(pady=(0, 10))
        self.entry.bind("<Return>", lambda _e: self._handle_login())

        # Remember me checkbox
        self.remember_var = tkinter.BooleanVar(value=True)
        remember_cb = ctk.CTkCheckBox(
            panel,
            text="Remember me",
            variable=self.remember_var,
            font=ctk.CTkFont(*FONTS["small"]),
            fg_color=COLORS["accent"],
            border_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            checkbox_width=18,
            checkbox_height=18,
        )
        remember_cb.pack(pady=(0, 15))

        # Login button
        self.login_btn = ctk.CTkButton(
            panel,
            text="Sign In",
            command=self._handle_login,
            width=300,
            height=42,
            font=ctk.CTkFont(*FONTS["button"]),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=8,
        )
        self.login_btn.pack()

        # Admin button (small, subtle)
        self.admin_btn = ctk.CTkButton(
            panel,
            text="Admin",
            command=self._handle_admin,
            width=100,
            height=28,
            font=ctk.CTkFont("Segoe UI", 10),
            fg_color="transparent",
            hover_color=COLORS["sidebar_hover"],
            text_color=COLORS["text_muted"],
            corner_radius=4,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.admin_btn.pack(pady=(8, 0))

        # Error label (hidden initially)
        self.error_label = ctk.CTkLabel(
            panel,
            text="",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["danger"],
        )
        self.error_label.pack(pady=(15, 0))

        # Status bar at bottom
        status = ctk.CTkLabel(
            panel,
            text="X1YEH Services  |  v1.0.0",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"],
        )
        status.pack(side="bottom", pady=(0, 18))

        self.particles.start()

    def _handle_login(self):
        key = self.entry_var.get().strip()
        if not key:
            self._show_error("Please enter a license key.")
            return
        self.login_btn.configure(state="disabled", text="Signing in...")
        self.error_label.configure(text="")
        self.on_login(key)

    def _handle_admin(self):
        if self.on_admin:
            AdminKeyDialog(self.winfo_toplevel(), on_submit=self.on_admin)

    def _show_error(self, msg: str):
        self.error_label.configure(text=msg)

    def set_loading(self, loading: bool):
        if loading:
            self.login_btn.configure(state="disabled", text="Signing in...")
        else:
            self.login_btn.configure(state="normal", text="Sign In")

    def on_login_error(self, message: str):
        self._show_error(message)
        self.login_btn.configure(state="normal", text="Sign In")

    def destroy_particles(self):
        self.particles.stop()


# ---------------------------------------------------------------------------
# Dashboard Frame
# ---------------------------------------------------------------------------

class DashboardFrame(ctk.CTkFrame):
    """Main dashboard view showing license status and stats."""

    def __init__(self, parent, profile: dict):
        super().__init__(parent, fg_color="transparent")
        self._build(profile)

    def _build(self, profile: dict):
        header = ctk.CTkLabel(
            self,
            text="Dashboard",
            font=ctk.CTkFont(*FONTS["heading"]),
            text_color=COLORS["text_primary"],
        )
        header.pack(anchor="w", pady=(10, 20))

        # Stats grid
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x")

        stats = [
            ("License Status", profile.get("license_status", "Active"), COLORS["success"] if profile.get("license_status") == "Active" else COLORS["danger"]),
            ("Username", profile.get("username", "N/A"), COLORS["text_primary"]),
            ("Expiry Date", profile.get("expiry_date", "N/A"), COLORS["text_secondary"]),
            ("Version", profile.get("version", "N/A"), COLORS["text_secondary"]),
            ("Server", profile.get("server", "N/A"), COLORS["text_secondary"]),
        ]

        for idx, (label, value, color) in enumerate(stats):
            card = GlassCard(stats_frame)
            row, col = divmod(idx, 3)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                card,
                text=label,
                font=ctk.CTkFont(*FONTS["small"]),
                text_color=COLORS["text_muted"],
            ).grid(row=0, column=0, padx=16, pady=(14, 2), sticky="w")
            ctk.CTkLabel(
                card,
                text=str(value),
                font=ctk.CTkFont(*FONTS["subheading"]),
                text_color=color,
            ).grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")

        for i in range(3):
            stats_frame.grid_columnconfigure(i, weight=1, uniform="stats")

        # Account stats section
        acct_header = ctk.CTkLabel(
            self,
            text="Account Statistics",
            font=ctk.CTkFont(*FONTS["subheading"]),
            text_color=COLORS["text_primary"],
        )
        acct_header.pack(anchor="w", pady=(25, 10))

        acct_frame = ctk.CTkFrame(self, fg_color="transparent")
        acct_frame.pack(fill="x")

        acct_stats = profile.get("account_stats", {})
        acct_items = [
            ("Generated Today", str(acct_stats.get("generated_today", 0))),
            ("Total Generated", str(acct_stats.get("total_generated", 0))),
            ("Categories", str(acct_stats.get("categories", 0))),
        ]
        for idx, (label, value) in enumerate(acct_items):
            card = GlassCard(acct_frame)
            card.grid(row=0, column=idx, padx=8, pady=4, sticky="nsew")
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                card,
                text=label,
                font=ctk.CTkFont(*FONTS["small"]),
                text_color=COLORS["text_muted"],
            ).grid(row=0, column=0, padx=16, pady=(14, 2), sticky="w")
            ctk.CTkLabel(
                card,
                text=value,
                font=ctk.CTkFont(size=22, weight="bold"),
                text_color=COLORS["accent"],
            ).grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")

        for i in range(3):
            acct_frame.grid_columnconfigure(i, weight=1, uniform="acct")

        # Recent activity
        rec_header = ctk.CTkLabel(
            self,
            text="Recent Activity",
            font=ctk.CTkFont(*FONTS["subheading"]),
            text_color=COLORS["text_primary"],
        )
        rec_header.pack(anchor="w", pady=(25, 10))

        activity_list = profile.get("recent_activity", [])
        activity_card = GlassCard(self)
        activity_card.pack(fill="both", expand=True)

        if not activity_list:
            ctk.CTkLabel(
                activity_card,
                text="No recent activity",
                font=ctk.CTkFont(*FONTS["small"]),
                text_color=COLORS["text_muted"],
            ).pack(padx=20, pady=20)
        else:
            for act in activity_list[:8]:
                row_frame = ctk.CTkFrame(activity_card, fg_color="transparent")
                row_frame.pack(fill="x", padx=12, pady=4)
                dot_color = COLORS["success"] if "generated" in act.get("action", "").lower() else COLORS["accent"]
                ctk.CTkLabel(
                    row_frame,
                    text="●",
                    font=ctk.CTkFont(size=8),
                    text_color=dot_color,
                ).pack(side="left", padx=(4, 8))
                ctk.CTkLabel(
                    row_frame,
                    text=act.get("description", ""),
                    font=ctk.CTkFont(*FONTS["small"]),
                    text_color=COLORS["text_secondary"],
                ).pack(side="left")
                ctk.CTkLabel(
                    row_frame,
                    text=act.get("timestamp", ""),
                    font=ctk.CTkFont(*FONTS["small"]),
                    text_color=COLORS["text_muted"],
                ).pack(side="right", padx=8)


# ---------------------------------------------------------------------------
# Generate Frame
# ---------------------------------------------------------------------------

class GenerateFrame(ctk.CTkFrame):
    """Account generation page with category cards and result display."""

    def __init__(
        self,
        parent,
        permissions: list[str],
        on_generate: Callable[[str], None],
    ):
        super().__init__(parent, fg_color="transparent")
        self.permissions = permissions
        self.on_generate = on_generate
        self.selected_category: Optional[str] = None
        self.current_account: Optional[dict] = None
        self.generate_btn: Optional[ctk.CTkButton] = None
        self.copy_email_btn: Optional[ctk.CTkButton] = None
        self.copy_pass_btn: Optional[ctk.CTkButton] = None
        self.copy_all_btn: Optional[ctk.CTkButton] = None
        self._build()

    def _build(self):
        header = ctk.CTkLabel(
            self,
            text="Generate Account",
            font=ctk.CTkFont(*FONTS["heading"]),
            text_color=COLORS["text_primary"],
        )
        header.pack(anchor="w", pady=(10, 5))

        ctk.CTkLabel(
            self,
            text="Select a category below to generate an account",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", pady=(0, 20))

        # Category cards grid
        cat_container = ctk.CTkFrame(self, fg_color="transparent")
        cat_container.pack(fill="x")

        self.cat_buttons: dict[str, ctk.CTkButton] = {}
        cols = 4
        for idx, cat in enumerate(self.permissions):
            row, col = divmod(idx, cols)
            btn = ctk.CTkButton(
                cat_container,
                text=cat,
                font=ctk.CTkFont("Segoe UI", 13, "bold"),
                width=160,
                height=80,
                corner_radius=14,
                fg_color=COLORS["bg_card"],
                hover_color="#1a3350",
                border_color=COLORS["border"],
                border_width=1,
                command=lambda c=cat: self._select_category(c),
            )
            btn.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            self.cat_buttons[cat] = btn

        for i in range(cols):
            cat_container.grid_columnconfigure(i, weight=1)

        # Result area (hidden initially)
        self.result_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.result_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(*FONTS["subheading"]),
            text_color=COLORS["text_primary"],
        )
        self.result_text = ctk.CTkTextbox(
            self,
            height=100,
            font=ctk.CTkFont(*FONTS["mono"]),
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=8,
            wrap="word",
            state="disabled",
        )

    def _select_category(self, category: str):
        self.selected_category = category
        # Update button styles
        for cat, btn in self.cat_buttons.items():
            if cat == category:
                btn.configure(fg_color=COLORS["accent"], border_color=COLORS["accent"])
            else:
                btn.configure(fg_color=COLORS["bg_card"], border_color=COLORS["border"])

        # Show generate button
        self._show_result_area(category)

    def _show_result_area(self, category: str):
        # Clear previous result
        if self.result_frame.winfo_ismapped():
            self.result_frame.pack_forget()
        self.result_label.pack_forget()
        self.result_text.pack_forget()

        # Generate action bar
        self.result_label = ctk.CTkLabel(
            self,
            text=f"Category: {category}",
            font=ctk.CTkFont(*FONTS["subheading"]),
            text_color=COLORS["text_primary"],
        )
        self.result_label.pack(anchor="w", pady=(20, 10))

        self.generate_btn = ctk.CTkButton(
            self,
            text="Generate Account",
            command=lambda: self.on_generate(category),
            font=ctk.CTkFont(*FONTS["button"]),
            height=40,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        )
        self.generate_btn.pack(anchor="w", pady=(0, 15))

    def display_account(self, account: dict, remaining: int = 0):
        """Show the generated account details."""
        self.current_account = account
        self.generate_btn.configure(state="normal", text="Generate Another")

        email = account.get("email", account.get("username", "N/A"))
        password = account.get("password", "N/A")
        display = f"Email/Username: {email}\nPassword: {password}\n\nRemaining today: {remaining}"

        if not self.result_text.winfo_ismapped():
            self.result_frame = ctk.CTkFrame(self, fg_color="transparent")
            self.result_text = ctk.CTkTextbox(
                self,
                height=100,
                font=ctk.CTkFont(*FONTS["mono"]),
                fg_color=COLORS["bg_input"],
                border_color=COLORS["border"],
                border_width=1,
                corner_radius=8,
                wrap="word",
                state="disabled",
            )
            self.result_text.pack(fill="x", pady=(0, 10))

            # Action buttons
            btn_frame = ctk.CTkFrame(self, fg_color="transparent")
            btn_frame.pack(fill="x", pady=(0, 10))

            btn_style = {
                "font": ctk.CTkFont(*FONTS["body"]),
                "height": 34,
                "corner_radius": 6,
                "fg_color": COLORS["bg_card"],
                "hover_color": COLORS["sidebar_hover"],
                "border_color": COLORS["border"],
                "border_width": 1,
            }

            self.copy_all_btn = ctk.CTkButton(
                btn_frame, text="Copy All",
                command=lambda: self._copy_to_clipboard(display),
                **btn_style,
            )
            self.copy_all_btn.pack(side="left", padx=(0, 8))

            self.copy_email_btn = ctk.CTkButton(
                btn_frame, text="Copy Email",
                command=lambda: self._copy_to_clipboard(email),
                **btn_style,
            )
            self.copy_email_btn.pack(side="left", padx=(0, 8))

            self.copy_pass_btn = ctk.CTkButton(
                btn_frame, text="Copy Password",
                command=lambda: self._copy_to_clipboard(password),
                **btn_style,
            )
            self.copy_pass_btn.pack(side="left")

        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", display)
        self.result_text.configure(state="disabled")

        Toast.show(self, "Account generated successfully!", "success")

    def set_generating(self, generating: bool):
        if self.generate_btn:
            if generating:
                self.generate_btn.configure(state="disabled", text="Generating...")
            else:
                self.generate_btn.configure(state="normal", text="Generate Account")

    @staticmethod
    def _copy_to_clipboard(text: str):
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
            root.destroy()
        except Exception:
            import subprocess
            escaped = text.replace("'", "''")
            try:
                subprocess.run(
                    ["powershell", "-Command", f"Set-Clipboard -Value '{escaped}'"],
                    capture_output=True, timeout=3,
                )
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Stock Frame
# ---------------------------------------------------------------------------

class StockFrame(ctk.CTkFrame):
    """Stock overview page showing available accounts."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._build()
        self._stock_data: Optional[dict] = None

    def _build(self):
        header = ctk.CTkLabel(
            self,
            text="Account Stock",
            font=ctk.CTkFont(*FONTS["heading"]),
            text_color=COLORS["text_primary"],
        )
        header.pack(anchor="w", pady=(10, 20))

        # Summary cards
        self.summary_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.summary_frame.pack(fill="x")

        summary_items = [
            ("available_accounts", "Available"),
            ("generated_today", "Generated Today"),
            ("remaining", "Remaining"),
        ]

        self.summary_labels: dict[str, ctk.CTkLabel] = {}
        for idx, (key, label) in enumerate(summary_items):
            card = GlassCard(self.summary_frame)
            card.grid(row=0, column=idx, padx=8, pady=4, sticky="nsew")
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                card,
                text=label,
                font=ctk.CTkFont(*FONTS["small"]),
                text_color=COLORS["text_muted"],
            ).grid(row=0, column=0, padx=16, pady=(14, 2), sticky="w")
            val_lbl = ctk.CTkLabel(
                card,
                text="--",
                font=ctk.CTkFont(size=22, weight="bold"),
                text_color=COLORS["accent"],
            )
            val_lbl.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")
            self.summary_labels[key] = val_lbl

        for i in range(3):
            self.summary_frame.grid_columnconfigure(i, weight=1, uniform="stock_summary")

        # Last updated
        self.updated_label = ctk.CTkLabel(
            self,
            text="Last updated: --",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"],
        )
        self.updated_label.pack(anchor="w", pady=(5, 15))

        # Per-category stock
        ctk.CTkLabel(
            self,
            text="Per Category",
            font=ctk.CTkFont(*FONTS["subheading"]),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", pady=(10, 10))

        self.cat_container = ctk.CTkFrame(self, fg_color="transparent")
        self.cat_container.pack(fill="both", expand=True)

        self.cat_widgets: dict[str, ctk.CTkProgressBar] = {}

        # Refresh button
        self.refresh_btn = ctk.CTkButton(
            self,
            text="Refresh Stock",
            command=self._on_refresh,
            font=ctk.CTkFont(*FONTS["body"]),
            height=34,
            corner_radius=6,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["sidebar_hover"],
            border_color=COLORS["border"],
            border_width=1,
        )

    def _on_refresh(self):
        pass  # handled by MainApp callback

    def update_stock(self, data: dict):
        self._stock_data = data
        self.summary_labels["available_accounts"].configure(
            text=str(data.get("available_accounts", 0))
        )
        self.summary_labels["generated_today"].configure(
            text=str(data.get("generated_today", 0))
        )
        self.summary_labels["remaining"].configure(
            text=str(data.get("remaining", 0))
        )
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.updated_label.configure(text=f"Last updated: {ts}")

        categories = data.get("categories", {})
        for widget in self.cat_container.winfo_children():
            widget.destroy()
        self.cat_widgets.clear()

        if not categories:
            ctk.CTkLabel(
                self.cat_container,
                text="No stock data available",
                font=ctk.CTkFont(*FONTS["small"]),
                text_color=COLORS["text_muted"],
            ).pack(pady=20)
            return

        row_idx = 0
        for cat_name, cat_data in categories.items():
            row_frame = ctk.CTkFrame(self.cat_container, fg_color="transparent")
            row_frame.pack(fill="x", pady=3)

            total = cat_data.get("total", 0)
            used = cat_data.get("used", 0)
            remaining_val = total - used
            pct = (remaining_val / total * 100) if total > 0 else 0

            ctk.CTkLabel(
                row_frame,
                text=cat_name,
                font=ctk.CTkFont(*FONTS["body"]),
                text_color=COLORS["text_secondary"],
                width=120,
                anchor="w",
            ).pack(side="left", padx=(0, 8))

            bar = ctk.CTkProgressBar(
                row_frame,
                width=200,
                progress_color=COLORS["accent"],
                fg_color=COLORS["bg_input"],
                height=8,
                corner_radius=4,
            )
            bar.set(pct / 100)
            bar.pack(side="left", padx=(0, 8))

            ctk.CTkLabel(
                row_frame,
                text=f"{remaining_val}/{total}",
                font=ctk.CTkFont(*FONTS["small"]),
                text_color=COLORS["text_secondary"],
                width=60,
                anchor="e",
            ).pack(side="right")

            self.cat_widgets[cat_name] = bar
            row_idx += 1

        if not self.refresh_btn.winfo_ismapped():
            self.refresh_btn.pack(side="bottom", pady=(10, 20))


# ---------------------------------------------------------------------------
# Settings Frame
# ---------------------------------------------------------------------------

class SettingsFrame(ctk.CTkFrame):
    """Settings page with configurable options."""

    def __init__(self, parent, config: dict, on_save: Callable[[dict], None]):
        super().__init__(parent, fg_color="transparent")
        self.config = config.copy()
        self.on_save = on_save
        self._build()

    def _build(self):
        header = ctk.CTkLabel(
            self,
            text="Settings",
            font=ctk.CTkFont(*FONTS["heading"]),
            text_color=COLORS["text_primary"],
        )
        header.pack(anchor="w", pady=(10, 20))

        settings = [
            ("theme", "Theme", ["dark", "light"]),
            ("launch_on_startup", "Launch on Startup", None),
            ("remember_login", "Remember Login", None),
            ("animations", "Animations", None),
            ("notification_sounds", "Notification Sounds", None),
            ("check_for_updates", "Check for Updates", None),
        ]

        self.widgets: dict = {}

        for key, label, options in settings:
            card = GlassCard(self)
            card.pack(fill="x", pady=4)

            ctk.CTkLabel(
                card,
                text=label,
                font=ctk.CTkFont(*FONTS["body"]),
                text_color=COLORS["text_primary"],
            ).pack(side="left", padx=16, pady=12)

            value = self.config.get(key, False)

            if options:
                var = tkinter.StringVar(value=value)
                widget = ctk.CTkOptionMenu(
                    card,
                    variable=var,
                    values=options,
                    font=ctk.CTkFont(*FONTS["small"]),
                    fg_color=COLORS["bg_input"],
                    button_color=COLORS["accent"],
                    button_hover_color=COLORS["accent_hover"],
                    dropdown_fg_color=COLORS["bg_card"],
                    width=120,
                )
                widget.pack(side="right", padx=16, pady=12)
                self.widgets[key] = var
            else:
                var = tkinter.BooleanVar(value=value)
                widget = ctk.CTkSwitch(
                    card,
                    variable=var,
                    text="",
                    fg_color=COLORS["accent"],
                    button_color=COLORS["accent_light"],
                    button_hover_color=COLORS["accent_hover"],
                    progress_color=COLORS["accent"],
                    width=44,
                )
                widget.pack(side="right", padx=16, pady=12)
                self.widgets[key] = var

        # Save button
        save_btn = ctk.CTkButton(
            self,
            text="Save Settings",
            command=self._save,
            font=ctk.CTkFont(*FONTS["button"]),
            height=40,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        )
        save_btn.pack(pady=(20, 0))

    def _save(self):
        for key, widget in self.widgets.items():
            self.config[key] = widget.get()
        self.on_save(self.config)
        Toast.show(self, "Settings saved successfully!", "success")


# ---------------------------------------------------------------------------
# About Frame
# ---------------------------------------------------------------------------

class AboutFrame(ctk.CTkFrame):
    """About page."""

    def __init__(self, parent, version: str = "1.0.0"):
        super().__init__(parent, fg_color="transparent")
        self._build(version)

    def _build(self, version: str):
        # Center everything
        spacer_top = ctk.CTkFrame(self, height=60, fg_color="transparent")
        spacer_top.pack()

        about_logo = load_logo((80, 80))
        if about_logo:
            logo = ctk.CTkLabel(self, image=about_logo, text="")
            logo.pack()
        else:
            logo = ctk.CTkLabel(
                self,
                text=APP_TITLE,
                font=ctk.CTkFont("Segoe UI", 24, "bold"),
                text_color=COLORS["accent"],
            )
            logo.pack()

        ctk.CTkLabel(
            self,
            text=APP_TITLE,
            font=ctk.CTkFont(*FONTS["heading"]),
            text_color=COLORS["text_primary"],
        ).pack(pady=(5, 5))

        ctk.CTkLabel(
            self,
            text=f"Version {version}",
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text_secondary"],
        ).pack()

        ctk.CTkLabel(
            self,
            text="A modern account management tool.\nSecurely generate and manage accounts\nfrom your licensed categories.",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"],
            justify="center",
        ).pack(pady=(20, 30))

        ctk.CTkLabel(
            self,
            text="Built with Python • CustomTkinter • FastAPI",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"],
        ).pack(side="bottom", pady=(0, 20))


# ---------------------------------------------------------------------------
# Update Dialog
# ---------------------------------------------------------------------------

class UpdateDialog(ctk.CTkToplevel):
    """Modal dialog showing update information."""

    def __init__(self, parent, update_info: dict, on_update: Callable, on_skip: Callable):
        super().__init__(parent)
        self.title("Update Available")
        self.geometry("420x340")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg_secondary"])
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w, h = 420, 340
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

        self._build(update_info, on_update, on_skip)

    def _build(self, info: dict, on_update: Callable, on_skip: Callable):
        ctk.CTkLabel(
            self,
            text="Update Available",
            font=ctk.CTkFont(*FONTS["heading"]),
            text_color=COLORS["text_primary"],
        ).pack(pady=(30, 10))

        ctk.CTkLabel(
            self,
            text=f"Current: {info.get('current', '?')}  →  Latest: {info.get('version', '?')}",
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["accent"],
        ).pack(pady=(0, 15))

        notes = info.get("notes", "A new version is available.")
        ctk.CTkLabel(
            self,
            text=notes,
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_secondary"],
            wraplength=360,
            justify="center",
        ).pack(pady=(0, 25))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack()

        ctk.CTkButton(
            btn_frame,
            text="Update Now",
            command=lambda: [self.destroy(), on_update()],
            font=ctk.CTkFont(*FONTS["button"]),
            width=140,
            height=38,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            corner_radius=8,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_frame,
            text="Later",
            command=lambda: [self.destroy(), on_skip()],
            font=ctk.CTkFont(*FONTS["button"]),
            width=140,
            height=38,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["sidebar_hover"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=8,
        ).pack(side="left", padx=8)


# ---------------------------------------------------------------------------
# Main Application Window
# ---------------------------------------------------------------------------

class MainApp(ctk.CTkFrame):
    """Main application frame with sidebar navigation and content pages."""

    def __init__(
        self,
        parent,
        api_client,
        config: dict,
        profile: dict,
        permissions: list[str],
        on_logout: Callable,
        is_admin: bool = False,
    ):
        super().__init__(parent, fg_color="transparent")
        self.root = parent
        self.api = api_client
        self.config = config
        self.profile = profile
        self.permissions = permissions
        self.on_logout = on_logout
        self.is_admin = is_admin
        self.current_page: Optional[str] = None

        self.pack(fill="both", expand=True)
        self._build_layout()
        self._show_page("dashboard")

    # --- layout -------------------------------------------------------------

    def _build_layout(self):
        # Main container
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar = ctk.CTkFrame(
            self.main_container,
            fg_color=COLORS["bg_sidebar"],
            width=200,
            corner_radius=0,
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Sidebar header with logo
        sidebar_logo = load_logo((40, 40))
        if sidebar_logo:
            ctk.CTkLabel(self.sidebar, image=sidebar_logo, text="").pack(pady=(24, 8))
        ctk.CTkLabel(
            self.sidebar,
            text="X1YEH Services",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=COLORS["text_primary"],
        ).pack(pady=(0, 6))
        ctk.CTkLabel(
            self.sidebar,
            text="Account Generator",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=COLORS["text_muted"],
        ).pack(pady=(0, 16))

        # Separator
        sep = ctk.CTkFrame(self.sidebar, height=1, fg_color=COLORS["border"])
        sep.pack(fill="x", padx=16, pady=(0, 12))

        # Nav buttons
        nav_items = [
            ("dashboard", "Dashboard"),
            ("generate", "Generate"),
            ("stock", "Stock"),
            ("settings", "Settings"),
            ("about", "About"),
        ]
        if self.is_admin:
            nav_items.append(("admin", "Admin"))

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for page_id, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                font=ctk.CTkFont(*FONTS["sidebar"]),
                anchor="w",
                height=42,
                corner_radius=8,
                fg_color="transparent",
                hover_color=COLORS["sidebar_hover"],
                text_color=COLORS["text_secondary"],
                command=lambda p=page_id: self._show_page(p),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[page_id] = btn

        # Spacer
        ctk.CTkFrame(self.sidebar, fg_color="transparent").pack(fill="both", expand=True)

        # Logout button at bottom
        ctk.CTkButton(
            self.sidebar,
            text="Sign Out",
            font=ctk.CTkFont(*FONTS["small"]),
            height=34,
            corner_radius=6,
            fg_color="transparent",
            hover_color=COLORS["sidebar_hover"],
            text_color=COLORS["text_muted"],
            command=self._handle_logout,
        ).pack(fill="x", padx=10, pady=(0, 20))

        # Content area
        self.content_frame = ctk.CTkFrame(
            self.main_container, fg_color="transparent"
        )
        self.content_frame.pack(side="left", fill="both", expand=True, padx=4)

        self.pages: dict[str, ctk.CTkFrame] = {}

    # --- page management ----------------------------------------------------

    def _show_page(self, page_id: str):
        if self.current_page == page_id:
            return

        # Update nav button styles
        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.configure(
                    fg_color=COLORS["sidebar_active"],
                    text_color=COLORS["accent_light"],
                    border_width=0,
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=COLORS["text_secondary"],
                )

        # Hide current page
        if self.current_page and self.current_page in self.pages:
            self.pages[self.current_page].pack_forget()

        # Create page if needed
        if page_id not in self.pages:
            page = self._create_page(page_id)
            self.pages[page_id] = page

        self.pages[page_id].pack(fill="both", expand=True, padx=24, pady=10)
        self.current_page = page_id

    def _create_page(self, page_id: str) -> ctk.CTkFrame:
        if page_id == "dashboard":
            return DashboardFrame(self.content_frame, self.profile)
        elif page_id == "generate":
            return GenerateFrame(
                self.content_frame,
                permissions=self.permissions,
                on_generate=self._handle_generate,
            )
        elif page_id == "stock":
            frame = StockFrame(self.content_frame)
            frame.refresh_btn.configure(command=self._handle_stock_refresh)
            self._handle_stock_refresh()
            return frame
        elif page_id == "settings":
            return SettingsFrame(
                self.content_frame,
                config=self.config,
                on_save=self._handle_save_settings,
            )
        elif page_id == "about":
            return AboutFrame(self.content_frame, version=self.config.get("version", "1.0.0"))
        elif page_id == "admin":
            return AdminFrame(self.content_frame, self.api)
        return ctk.CTkFrame(self.content_frame)

    # --- handlers -----------------------------------------------------------

    def _handle_generate(self, category: str):
        page = self.pages.get("generate")
        if not isinstance(page, GenerateFrame):
            return
        page.set_generating(True)
        self.api.generate_account_async(
            category,
            callback=lambda result: self._on_generate_result(result),
        )

    def _on_generate_result(self, result: dict):
        page = self.pages.get("generate")
        if not isinstance(page, GenerateFrame):
            return
        page.set_generating(False)
        if result.get("success", True):
            account = result.get("account", result)
            remaining = result.get("remaining_today", 0)
            page.display_account(account, remaining)
            Toast.show(self.winfo_toplevel(), f"Generated! {remaining} left today.", "success")
        else:
            error = result.get("error", "Failed to generate account.")
            Toast.show(self.winfo_toplevel(), error, "error")

    def _handle_stock_refresh(self):
        self.api.get_stock_async(callback=self._on_stock_result)

    def _on_stock_result(self, result: dict):
        page = self.pages.get("stock")
        if not isinstance(page, StockFrame):
            return
        if result.get("success", True):
            page.update_stock(result)
        else:
            Toast.show(self, result.get("error", "Failed to load stock."), "error")

    def _handle_save_settings(self, new_config: dict):
        self.config.update(new_config)
        try:
            config_path = os.path.join(os.path.dirname(sys.executable), "config.json")
            if not os.path.exists(config_path):
                config_path = os.path.join(os.path.dirname(__file__), "config.json")
            with open(config_path, "w") as fh:
                json.dump(self.config, fh, indent=2)
        except Exception:
            pass

    def _handle_logout(self):
        self.api.logout()
        self.destroy()
        self.on_logout()

    # --- public API ---------------------------------------------------------

    def show_update_dialog(self, update_info: dict, on_update: Callable, on_skip: Callable):
        UpdateDialog(self, update_info, on_update, on_skip)

    def show_error(self, message: str):
        Toast.show(self, message, "error")
