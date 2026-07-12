"""
Local Flask Server
Runs alongside the app on localhost. Provides all API endpoints.
Wraps the storage module for license validation, account generation, stock, etc.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import logging

from flask import Flask, request, jsonify

import storage

# Suppress Flask/Werkzeug banner and request logs in production
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)
cli = logging.getLogger("flask.app")
cli.setLevel(logging.ERROR)

app = Flask(__name__)

# In-memory token -> license_key mapping
_tokens: dict[str, str] = {}


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    key = data.get("license_key", "").strip()
    if not key:
        return jsonify({"success": False, "error": "License key required."})

    result = storage.validate_license(key)
    if result is None:
        return jsonify({"success": False, "error": "Invalid or expired license key."})

    _tokens[result["token"]] = key
    return jsonify({
        "success": True,
        "token": result["token"],
        "license_key": key,
        "username": result["username"],
    })


# ---------------------------------------------------------------------------
# GET /profile
# ---------------------------------------------------------------------------

@app.route("/profile", methods=["GET"])
def profile():
    lic = _get_license()
    if not lic:
        return jsonify({"success": False, "error": "Unauthorized."})
    data = storage.get_profile(lic)
    return jsonify(data)


# ---------------------------------------------------------------------------
# GET /permissions
# ---------------------------------------------------------------------------

@app.route("/permissions", methods=["GET"])
def permissions():
    lic = _get_license()
    if not lic:
        return jsonify({"success": False, "error": "Unauthorized."})
    result = storage.validate_license(lic)
    if result is None:
        return jsonify({"success": False, "error": "License invalid."})
    return jsonify({"success": True, "permissions": result["permissions"]})


# ---------------------------------------------------------------------------
# POST /generate
# ---------------------------------------------------------------------------

@app.route("/generate", methods=["POST"])
def generate():
    lic = _get_license()
    if not lic:
        return jsonify({"success": False, "error": "Unauthorized."})

    data = request.get_json(silent=True) or {}
    category = data.get("category", "").strip()
    if not category:
        return jsonify({"success": False, "error": "Category required."})

    result = storage.validate_license(lic)
    if result is None:
        return jsonify({"success": False, "error": "License invalid."})

    if category not in result["permissions"]:
        return jsonify({"success": False, "error": f"Access denied for '{category}'."})

    daily_limit = result["daily_limit"]
    gen_result = storage.generate_account(lic, category, daily_limit)

    if not gen_result.get("success"):
        return jsonify(gen_result)

    return jsonify({
        "success": True,
        "account": gen_result["account"],
        "remaining_today": gen_result.get("remaining_today", 0),
    })


# ---------------------------------------------------------------------------
# GET /stock
# ---------------------------------------------------------------------------

@app.route("/stock", methods=["GET"])
def stock():
    return jsonify({**storage.get_stock(), "success": True})


# ---------------------------------------------------------------------------
# GET /version
# ---------------------------------------------------------------------------

@app.route("/version", methods=["GET"])
def version():
    import os
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.json")
        with open(path, "r") as fh:
            return jsonify(json.load(fh))
    except Exception:
        return jsonify({"version": "1.0.0", "download": "", "notes": ""})


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@app.route("/admin/licenses", methods=["GET"])
def admin_list_licenses():
    return jsonify({"success": True, "licenses": storage.list_licenses()})


@app.route("/admin/licenses", methods=["POST"])
def admin_create_license():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "User")
    permissions = data.get("permissions", [])
    daily_limit = data.get("daily_limit", 5)
    expiry_days = data.get("expiry_days", 365)
    result = storage.create_license(username, permissions, daily_limit, expiry_days)
    return jsonify({"success": True, **result})


@app.route("/admin/licenses/<int:license_id>", methods=["DELETE"])
def admin_delete_license(license_id: int):
    storage.delete_license(license_id)
    return jsonify({"success": True})


@app.route("/admin/licenses/<license_key>/revoke", methods=["POST"])
def admin_revoke_license(license_key: str):
    storage.revoke_license(license_key)
    return jsonify({"success": True})


@app.route("/admin/stock", methods=["GET"])
def admin_get_stock():
    stock_data = storage.get_stock()
    all_accounts = []
    for cat in stock_data.get("categories", {}):
        all_accounts.extend(storage.get_accounts_by_category(cat))
    return jsonify({"success": True, "accounts": all_accounts, "summary": stock_data})


@app.route("/admin/stock", methods=["POST"])
def admin_add_stock():
    data = request.get_json(silent=True) or {}
    category = data.get("category", "")
    email = data.get("email", "")
    password = data.get("password", "")
    if not category or not email or not password:
        return jsonify({"success": False, "error": "category, email, and password required."})
    storage.add_account(category, email, password)
    return jsonify({"success": True})


@app.route("/admin/stock/bulk", methods=["POST"])
def admin_add_stock_bulk():
    data = request.get_json(silent=True) or {}
    entries = data.get("entries", [])
    if not entries:
        return jsonify({"success": False, "error": "entries required."})
    count = storage.add_accounts_bulk([(e["category"], e["email"], e["password"]) for e in entries])
    return jsonify({"success": True, "added": count})


@app.route("/admin/logs", methods=["GET"])
def admin_logs():
    return jsonify({
        "success": True,
        "admin_logs": storage.get_admin_logs(),
        "gen_logs": storage.get_gen_logs(),
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_license() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        return _tokens.get(token)
    return None


# ---------------------------------------------------------------------------
# Server runner
# ---------------------------------------------------------------------------

def run_server(host: str = "127.0.0.1", port: int = 8099) -> threading.Thread | None:
    """Start Flask in a daemon thread. Returns the thread or None if port is busy."""
    import socket
    # Check if port is already in use (previous instance)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        sock.close()
    except OSError:
        # Port already in use, likely another instance running
        return None

    t = threading.Thread(
        target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    t.start()
    time.sleep(0.3)
    return t
