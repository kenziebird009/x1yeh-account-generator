"""
API Client Module
Handles all HTTPS communication with the backend server.
Includes secure token storage, background threading, and error handling.
"""

from __future__ import annotations

import json
import os
import time
import threading
from typing import Any, Callable, Optional

import requests
import base64
import hashlib
import uuid

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


# ---------------------------------------------------------------------------
# Secure local storage helpers
# ---------------------------------------------------------------------------

def _derive_key(machine_id: str) -> bytes:
    """Derive an encryption key from a machine-specific identifier."""
    if _CRYPTO_AVAILABLE:
        salt = b"accgen_salt_2024_v1"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
            backend=default_backend(),
        )
        return base64.urlsafe_b64encode(kdf.derive(machine_id.encode()))
    else:
        return base64.urlsafe_b64encode(
            hashlib.sha256((machine_id + "_salt").encode()).digest()
        )


def _get_machine_id() -> str:
    """Return a stable machine identifier."""
    try:
        raw = str(uuid.getnode()) + platform_id()
    except Exception:
        raw = str(uuid.getnode())
    return hashlib.sha256(raw.encode()).hexdigest()


def platform_id() -> str:
    """Return a platform-specific identifier string."""
    try:
        import subprocess
        result = subprocess.run(
            ["wmic", "csproduct", "get", "uuid"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return os.environ.get("COMPUTERNAME", "unknown")


def _get_storage_path() -> str:
    """Path to the encrypted token file."""
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    folder = os.path.join(base, "AccountGenerator")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "secure.dat")


def _encrypt(data: str) -> bytes:
    if _CRYPTO_AVAILABLE:
        key = _derive_key(_get_machine_id())
        f = Fernet(key)
        return f.encrypt(data.encode())
    else:
        key = _derive_key(_get_machine_id())
        data_bytes = data.encode()
        encoded = base64.urlsafe_b64encode(data_bytes)
        obfuscated = bytes(a ^ b for a, b in zip(encoded, key * (len(encoded) // len(key) + 1)))
        return base64.urlsafe_b64encode(obfuscated)


def _decrypt(encrypted: bytes) -> str:
    if _CRYPTO_AVAILABLE:
        key = _derive_key(_get_machine_id())
        f = Fernet(key)
        return f.decrypt(encrypted).decode()
    else:
        key = _derive_key(_get_machine_id())
        obfuscated = base64.urlsafe_b64decode(encrypted)
        encoded = bytes(a ^ b for a, b in zip(obfuscated, key * (len(obfuscated) // len(key) + 1)))
        return base64.urlsafe_b64decode(encoded).decode()


def save_credentials(license_key: str, token: str) -> None:
    """Securely store license key and auth token."""
    payload = json.dumps({"license": license_key, "token": token})
    encrypted = _encrypt(payload)
    path = _get_storage_path()
    with open(path, "wb") as fh:
        fh.write(encrypted)


def load_credentials() -> Optional[dict[str, str]]:
    """Load securely stored credentials."""
    path = _get_storage_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as fh:
            encrypted = fh.read()
        data = _decrypt(encrypted)
        return json.loads(data)
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        return None


def clear_credentials() -> None:
    """Remove stored credentials."""
    path = _get_storage_path()
    if os.path.exists(path):
        os.remove(path)


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------

class APIClient:
    """Thread-safe HTTPS client for the account generator backend."""

    def __init__(self, base_url: str = "https://api.example.com", timeout: int = 15):
        self.base_url: str = base_url.rstrip("/")
        self.timeout: int = timeout
        self.token: Optional[str] = None
        self._lock = threading.Lock()

    # --- internal helpers ---------------------------------------------------

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        t = timeout or self.timeout
        try:
            resp = requests.request(
                method, url, json=data, headers=self._headers(), timeout=t
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out."}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Cannot connect to server."}
        except requests.exceptions.HTTPError as exc:
            try:
                detail = exc.response.json()
                return {"success": False, "error": detail.get("detail", str(exc))}
            except Exception:
                return {"success": False, "error": f"Server error ({exc.response.status_code})."}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _async_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict],
        callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """Run a request in a background thread and invoke callback with result."""

        def worker() -> None:
            result = self._request(method, endpoint, data)
            callback(result)

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    # --- public API methods -------------------------------------------------

    def login(self, license_key: str) -> dict[str, Any]:
        """POST /login — validate license key and receive auth token."""
        result = self._request("POST", "/login", {"license_key": license_key})
        if result.get("success", True):
            token = result.get("token")
            if token:
                self.token = token
                save_credentials(license_key, token)
        return result

    def login_async(
        self, license_key: str, callback: Callable[[dict[str, Any]], None]
    ) -> None:
        self._async_request("POST", "/login", {"license_key": license_key}, callback)

    def get_profile(self) -> dict[str, Any]:
        """GET /profile — return user profile info."""
        return self._request("GET", "/profile")

    def get_profile_async(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._async_request("GET", "/profile", None, callback)

    def get_permissions(self) -> dict[str, Any]:
        """GET /permissions — return list of allowed categories."""
        return self._request("GET", "/permissions")

    def get_permissions_async(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._async_request("GET", "/permissions", None, callback)

    def generate_account(self, category: str) -> dict[str, Any]:
        """POST /generate — generate an account for the given category."""
        return self._request("POST", "/generate", {"category": category})

    def generate_account_async(
        self, category: str, callback: Callable[[dict[str, Any]], None]
    ) -> None:
        self._async_request("POST", "/generate", {"category": category}, callback)

    def get_stock(self) -> dict[str, Any]:
        """GET /stock — return stock information."""
        return self._request("GET", "/stock")

    def get_stock_async(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._async_request("GET", "/stock", None, callback)

    def get_version(self) -> dict[str, Any]:
        """GET /version — check for application updates."""
        return self._request("GET", "/version")

    def get_version_async(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._async_request("GET", "/version", None, callback)

    def restore_session(self) -> bool:
        """Attempt to restore a previous session from stored credentials."""
        creds = load_credentials()
        if not creds:
            return False
        self.token = creds.get("token")
        result = self.get_profile()
        if result.get("success", True):
            return True
        self.token = None
        clear_credentials()
        return False

    def logout(self) -> None:
        self.token = None
        clear_credentials()
