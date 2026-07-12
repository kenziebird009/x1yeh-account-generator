"""
Auto-Update Module
Checks version.json from a GitHub raw URL, downloads releases,
installs updates, and restarts the application.
"""

from __future__ import annotations

import json
import os
import sys
import shutil
import tempfile
import zipfile
import threading
import subprocess
from typing import Optional, Callable

import requests


class UpdateChecker:
    """Handles version checking, downloading, and installing updates.

    Works with GitHub Releases:
      - version_info_url: raw URL to version.json in repo
      - download_url: direct download of the release .zip / .exe
    """

    def __init__(
        self,
        current_version: str,
        version_info_url: str,
        app_dir: Optional[str] = None,
        timeout: int = 30,
    ):
        self.current_version: str = current_version
        self.version_info_url: str = version_info_url
        self.app_dir: str = app_dir or os.path.dirname(sys.executable)
        self.timeout: int = timeout
        self._download_in_progress: bool = False

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def check(self) -> Optional[dict]:
        """Return update info dict if a newer version exists, else None."""
        try:
            resp = requests.get(self.version_info_url, timeout=self.timeout)
            resp.raise_for_status()
            data: dict = resp.json()
        except Exception:
            return None

        latest = data.get("version", "0.0.0")
        if self._is_newer(latest, self.current_version):
            return {
                "version": latest,
                "download": data.get("download", ""),
                "notes": data.get("notes", ""),
                "current": self.current_version,
            }
        return None

    def download_and_install(
        self,
        update_info: dict,
        progress_callback: Optional[Callable[[float], None]] = None,
        done_callback: Optional[Callable[[bool, str], None]] = None,
    ) -> None:
        """Download, extract, install, and restart."""
        url = update_info.get("download", "")
        if not url or self._download_in_progress:
            if done_callback:
                done_callback(False, "Download in progress or no URL.")
            return

        self._download_in_progress = True

        def _worker() -> None:
            tmp_dir = None
            try:
                tmp_dir = tempfile.mkdtemp(prefix="x1yeh_update_")
                zip_path = os.path.join(tmp_dir, "update.zip")

                _download_file(url, zip_path, progress_callback)
                _extract_and_install(zip_path, self.app_dir)

                if done_callback:
                    done_callback(True, "")
                _request_restart()
            except Exception as exc:
                self._download_in_progress = False
                if done_callback:
                    done_callback(False, str(exc))
            finally:
                if tmp_dir and os.path.exists(tmp_dir):
                    try:
                        shutil.rmtree(tmp_dir, ignore_errors=True)
                    except Exception:
                        pass

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    @staticmethod
    def _is_newer(new_ver: str, cur_ver: str) -> bool:
        def _parse(v: str) -> tuple:
            parts = v.replace("v", "").replace("V", "").split(".")
            return tuple(int(p) if p.isdigit() else 0 for p in parts)
        return _parse(new_ver) > _parse(cur_ver)


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def _download_file(url: str, dest: str, progress_cb=None) -> None:
    """Stream a file to *dest* with optional progress callback."""
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0)) or None
    downloaded = 0
    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=65536):
            if not chunk:
                continue
            fh.write(chunk)
            downloaded += len(chunk)
            if progress_cb and total:
                progress_cb(min(downloaded / total, 1.0))


def _extract_and_install(zip_path: str, target_dir: str) -> None:
    """Extract a zip archive over the application directory."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            # skip folders
            if member.endswith("/") or member.endswith("\\"):
                continue
            src = zf.read(member)
            # flatten: take only the file name, ignore folder structure
            fname = os.path.basename(member)
            if not fname:
                continue
            dst = os.path.join(target_dir, fname)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as fh:
                fh.write(src)


def _request_restart() -> None:
    """Spawn a detached batch script that re-launches the app and exits."""
    exe = sys.executable
    cwd = os.path.dirname(exe)
    bat = (
        "@echo off\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        f'start "" "{exe}"\r\n'
        'del "%~f0"\r\n'
    )
    bat_path = os.path.join(tempfile.gettempdir(), "x1yeh_restart.bat")
    with open(bat_path, "w") as fh:
        fh.write(bat)
    subprocess.Popen(
        [bat_path],
        shell=True,
        creationflags=0x00000008,  # DETACHED_PROCESS
        cwd=cwd,
    )
    os._exit(0)


def ensure_app_folders(app_dir: str) -> list[str]:
    """Create all required folders for the app. Returns list of created paths."""
    folders = [
        os.path.join(app_dir, "assets"),
        os.path.join(app_dir, "data"),
    ]
    for f in folders:
        os.makedirs(f, exist_ok=True)
    return folders
