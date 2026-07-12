"""
API Client Module
Direct calls to storage functions — no HTTP server needed.
Provides async (threaded) wrappers for the GUI.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import uuid
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Secure local storage helpers
# ---------------------------------------------------------------------------

def _get_storage_path() -> str:
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    folder = os.path.join(base, "AccountGenerator")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "secure.dat")


def _machine_id() -> str:
    try:
        raw = str(uuid.getnode()) + (os.environ.get("COMPUTERNAME", ""))
    except Exception:
        raw = str(uuid.getnode())
    return hashlib.sha256(raw.encode()).hexdigest()


def _obfuscate(data: str) -> bytes:
    raw = data.encode()
    key = _machine_id().encode()
    key_bytes = (key * (len(raw) // len(key) + 1))[:len(raw)]
    return bytes(a ^ b for a, b in zip(raw, key_bytes))


def save_credentials(license_key: str, token: str) -> None:
    payload = json.dumps({"license": license_key, "token": token})
    with open(_get_storage_path(), "wb") as fh:
        fh.write(_obfuscate(payload))


def load_credentials() -> Optional[dict[str, str]]:
    path = _get_storage_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        decoded = _obfuscate(raw.decode("latin-1"))
        return json.loads(decoded)
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        return None


def clear_credentials() -> None:
    path = _get_storage_path()
    if os.path.exists(path):
        os.remove(path)


# ---------------------------------------------------------------------------
# APIClient — calls storage directly
# ---------------------------------------------------------------------------

class APIClient:
    """All API methods call the storage module directly. No HTTP server needed."""

    def __init__(self, base_url: str = ""):
        self.base_url = base_url
        self.token: Optional[str] = None
        self._license_key: Optional[str] = None
        self._lock = threading.Lock()

    def _run_async(self, func: Callable[[], Any], callback: Callable[[Any], None]) -> None:
        def _worker():
            try:
                result = func()
            except Exception as e:
                result = {"success": False, "error": str(e)}
            callback(result)
        threading.Thread(target=_worker, daemon=True).start()

    # --- auth ----------------------------------------------------------------

    def login(self, license_key: str) -> dict[str, Any]:
        import storage
        import storage as _s
        result = _s.validate_license(license_key)
        if result is None:
            return {"success": False, "error": "Invalid or expired license key."}
        self.token = result["token"]
        self._license_key = license_key
        save_credentials(license_key, result["token"])
        return {"success": True, "token": result["token"], "license_key": license_key, "username": result["username"]}

    def login_async(self, license_key: str, callback: Callable[[dict], None]) -> None:
        self._run_async(lambda: self.login(license_key), callback)

    def get_profile(self) -> dict[str, Any]:
        if not self._license_key:
            return {"success": False, "error": "Not logged in."}
        import storage as _s
        return _s.get_profile(self._license_key)

    def get_profile_async(self, callback: Callable[[dict], None]) -> None:
        self._run_async(self.get_profile, callback)

    def get_permissions(self) -> dict[str, Any]:
        if not self._license_key:
            return {"success": False, "error": "Not logged in."}
        import storage as _s
        result = _s.validate_license(self._license_key)
        if result is None:
            return {"success": False, "error": "License invalid."}
        return {"success": True, "permissions": result["permissions"]}

    def get_permissions_async(self, callback: Callable[[dict], None]) -> None:
        self._run_async(self.get_permissions, callback)

    def generate_account(self, category: str) -> dict[str, Any]:
        if not self._license_key:
            return {"success": False, "error": "Not logged in."}
        import storage as _s
        result = _s.validate_license(self._license_key)
        if result is None:
            return {"success": False, "error": "License invalid."}
        if category not in result["permissions"]:
            return {"success": False, "error": f"Access denied for '{category}'."}
        return _s.generate_account(self._license_key, category, result["daily_limit"])

    def generate_account_async(self, category: str, callback: Callable[[dict], None]) -> None:
        self._run_async(lambda: self.generate_account(category), callback)

    def get_stock(self) -> dict[str, Any]:
        import storage as _s
        data = _s.get_stock_summary()
        data["success"] = True
        return data

    def get_stock_async(self, callback: Callable[[dict], None]) -> None:
        self._run_async(self.get_stock, callback)

    def get_version(self) -> dict[str, Any]:
        try:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
            if not os.path.exists(config_path) and getattr(__import__("sys"), "frozen", False):
                config_path = os.path.join(getattr(__import__("sys"), "_MEIPASS", ""), "config.json")
            with open(config_path, "r") as fh:
                cfg = json.load(fh)
            return {"version": cfg.get("version", "1.0.0"), "download": cfg.get("github_releases", ""), "notes": ""}
        except Exception:
            return {"version": "1.0.0", "download": "", "notes": ""}

    def get_version_async(self, callback: Callable[[dict], None]) -> None:
        self._run_async(self.get_version, callback)

    def restore_session(self) -> bool:
        creds = load_credentials()
        if not creds:
            return False
        self.token = creds.get("token")
        self._license_key = creds.get("license")
        if not self._license_key:
            return False
        result = self.get_profile()
        return result.get("success", False)

    def logout(self) -> None:
        self.token = None
        self._license_key = None
        clear_credentials()


# ---------------------------------------------------------------------------
# Admin API — also calls storage directly
# ---------------------------------------------------------------------------

class AdminAPI:
    """All admin operations call storage directly."""

    @staticmethod
    def get_categories() -> dict:
        import storage as _s
        return {"success": True, "categories": _s.get_all_categories()}

    @staticmethod
    def list_licenses(search: str = "") -> dict:
        import storage as _s
        return {"success": True, "licenses": _s.list_licenses(search)}

    @staticmethod
    def create_license(
        username: str = "User",
        permissions: list[str] | None = None,
        daily_limit: int = 5,
        expiry_days: int | str | None = 365,
        max_uses: int | None = None,
        custom_expiry: str | None = None,
    ) -> dict:
        import storage as _s
        result = _s.create_license(
            username=username,
            permissions=permissions,
            daily_limit=daily_limit,
            expiry_days=expiry_days if not custom_expiry else 365,
            max_uses=max_uses,
            custom_expiry=custom_expiry,
        )
        return {"success": True, **result}

    @staticmethod
    def get_license(license_id: int) -> dict:
        import storage as _s
        lic = _s.get_license(license_id=license_id)
        if lic is None:
            return {"success": False, "error": "Not found."}
        return {"success": True, **lic}

    @staticmethod
    def update_license(license_id: int, **kwargs) -> dict:
        import storage as _s
        result = _s.update_license(license_id=license_id, **kwargs)
        if result is None:
            return {"success": False, "error": "Not found."}
        return {"success": True, **result}

    @staticmethod
    def delete_license(license_id: int) -> dict:
        import storage as _s
        ok = _s.delete_license(license_id)
        return {"success": ok}

    @staticmethod
    def toggle_license(license_id: int) -> dict:
        import storage as _s
        result = _s.toggle_license_status(license_id)
        if result is None:
            return {"success": False, "error": "Not found."}
        return {"success": True, **result}

    @staticmethod
    def get_license_stats() -> dict:
        import storage as _s
        return {"success": True, **_s.get_license_stats()}

    @staticmethod
    def get_stock(category: str = "", search: str = "", available_only: bool = False, limit: int = 1000) -> dict:
        import storage as _s
        accounts = _s.get_stock_accounts(category, search, available_only, limit)
        summary = _s.get_stock_summary()
        categories = _s.get_distinct_categories()
        return {"success": True, "accounts": accounts, "summary": summary, "categories": categories}

    @staticmethod
    def add_stock(category: str, email: str, password: str) -> dict:
        import storage as _s
        result = _s.add_account(category, email, password)
        if result is None:
            return {"success": False, "error": "Duplicate entry."}
        return {"success": True, **result}

    @staticmethod
    def add_stock_bulk(category: str, lines: str) -> dict:
        import storage as _s
        result = _s.add_accounts_bulk(category, lines)
        return {"success": True, **result}

    @staticmethod
    def delete_stock_account(account_id: int) -> dict:
        import storage as _s
        _s.delete_stock_account(account_id)
        return {"success": True}

    @staticmethod
    def clear_stock(category: str = "") -> dict:
        import storage as _s
        count = _s.clear_stock(category)
        return {"success": True, "deleted": count}

    @staticmethod
    def delete_used_stock() -> dict:
        import storage as _s
        count = _s.delete_used_stock()
        return {"success": True, "deleted": count}

    @staticmethod
    def dedup_stock() -> dict:
        import storage as _s
        result = _s.remove_duplicates()
        return {"success": True, **result}

    @staticmethod
    def export_stock(category: str = "") -> dict:
        import storage as _s
        data = _s.export_stock(category)
        return {"success": True, "data": data}

    @staticmethod
    def get_logs() -> dict:
        import storage as _s
        return {"success": True, "admin_logs": _s.get_admin_logs(), "gen_logs": _s.get_gen_logs()}

    @staticmethod
    def get_stats() -> dict:
        import storage as _s
        lic = _s.get_license_stats()
        stock = _s.get_stock_summary()
        gen_today = _s.get_today_count("*")
        gen_total = 0
        logs = _s.get_gen_logs()
        gen_total = len(logs)
        return {
            "success": True,
            "licenses": lic,
            "stock": {"total": stock["total_accounts"], "available": stock["available_accounts"], "used": stock["used_accounts"]},
            "generations": {"today": gen_today, "total": gen_total},
        }
