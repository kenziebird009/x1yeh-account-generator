"""
Local Flask Server — runs on 127.0.0.1:8099 alongside the app.
All REST endpoints for license validation, generation, stock, and admin.
"""

from __future__ import annotations

import json
import logging
import secrets
import socket
import threading
import time
from datetime import date
from typing import Any

from flask import Flask, request, jsonify

import storage

# Suppress Flask/Werkzeug logs in production
for _log_name in ("werkzeug", "flask.app"):
    l = logging.getLogger(_log_name)
    l.setLevel(logging.ERROR)

app = Flask(__name__)

# In-memory token → license_key mapping (resets on server restart)
_tokens: dict[str, str] = {}


def _auth() -> str | None:
    """Extract and validate the Bearer token from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        return _tokens.get(token)
    return None


def _require_auth():
    """Return license_key or abort with 401."""
    lic = _auth()
    if not lic:
        return None
    return lic


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    key = (data.get("license_key") or "").strip()
    if not key:
        return jsonify({"success": False, "error": "License key required."}), 400

    result = storage.validate_license(key)
    if result is None:
        return jsonify({"success": False, "error": "Invalid, expired, or disabled license key."}), 401

    _tokens[result["token"]] = key
    return jsonify({
        "success": True,
        "token": result["token"],
        "license_key": key,
        "username": result["username"],
    })


@app.route("/profile", methods=["GET"])
def profile():
    lic = _require_auth()
    if not lic:
        return jsonify({"success": False, "error": "Unauthorized."}), 401
    return jsonify(storage.get_profile(lic))


@app.route("/permissions", methods=["GET"])
def permissions():
    lic = _require_auth()
    if not lic:
        return jsonify({"success": False, "error": "Unauthorized."}), 401
    result = storage.validate_license(lic)
    if result is None:
        return jsonify({"success": False, "error": "License invalid."}), 401
    return jsonify({"success": True, "permissions": result["permissions"]})


@app.route("/generate", methods=["POST"])
def generate():
    lic = _require_auth()
    if not lic:
        return jsonify({"success": False, "error": "Unauthorized."}), 401

    data = request.get_json(silent=True) or {}
    category = (data.get("category") or "").strip()
    if not category:
        return jsonify({"success": False, "error": "Category required."}), 400

    result = storage.validate_license(lic)
    if result is None:
        return jsonify({"success": False, "error": "License invalid."}), 401

    if category not in result["permissions"]:
        return jsonify({"success": False, "error": f"Access denied for '{category}'."}), 403

    gen_result = storage.generate_account(lic, category, result["daily_limit"])
    return jsonify(gen_result)


@app.route("/stock", methods=["GET"])
def stock():
    return jsonify({"success": True, **storage.get_stock_summary()})


@app.route("/version", methods=["GET"])
def version():
    try:
        import os as _os
        path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "version.json")
        with open(path, "r") as fh:
            return jsonify(json.load(fh))
    except Exception:
        return jsonify({"version": "1.0.0", "download": "", "notes": ""})


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

# --- Categories ---

@app.route("/admin/categories", methods=["GET"])
def admin_categories():
    cats = storage.get_all_categories()
    return jsonify({"success": True, "categories": cats})


# --- Licenses ---

@app.route("/admin/licenses", methods=["GET"])
def admin_list_licenses():
    search = request.args.get("search", "")
    return jsonify({"success": True, "licenses": storage.list_licenses(search)})


@app.route("/admin/licenses", methods=["POST"])
def admin_create_license():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "User")
    permissions = data.get("permissions", [])
    daily_limit = int(data.get("daily_limit", 5))
    expiry = data.get("expiry", 365)
    max_uses = data.get("max_uses")
    if max_uses is not None:
        max_uses = int(max_uses)
    custom_expiry = data.get("custom_expiry")

    result = storage.create_license(
        username=username,
        permissions=permissions,
        daily_limit=daily_limit,
        expiry_days=expiry if not custom_expiry else 365,
        max_uses=max_uses,
        custom_expiry=custom_expiry,
    )
    return jsonify({"success": True, **result})


@app.route("/admin/licenses/<int:license_id>", methods=["GET"])
def admin_get_license(license_id: int):
    lic = storage.get_license(license_id=license_id)
    if lic is None:
        return jsonify({"success": False, "error": "Not found."}), 404
    return jsonify({"success": True, **lic})


@app.route("/admin/licenses/<int:license_id>", methods=["PUT"])
def admin_update_license(license_id: int):
    data = request.get_json(silent=True) or {}
    result = storage.update_license(
        license_id=license_id,
        username=data.get("username"),
        permissions=data.get("permissions"),
        daily_limit=data.get("daily_limit"),
        status=data.get("status"),
        expiry_date=data.get("expiry_date"),
        max_uses=data.get("max_uses"),
    )
    if result is None:
        return jsonify({"success": False, "error": "Not found."}), 404
    return jsonify({"success": True, **result})


@app.route("/admin/licenses/<int:license_id>", methods=["DELETE"])
def admin_delete_license(license_id: int):
    ok = storage.delete_license(license_id)
    if not ok:
        return jsonify({"success": False, "error": "Not found."}), 404
    return jsonify({"success": True})


@app.route("/admin/licenses/<int:license_id>/toggle", methods=["POST"])
def admin_toggle_license(license_id: int):
    result = storage.toggle_license_status(license_id)
    if result is None:
        return jsonify({"success": False, "error": "Not found."}), 404
    return jsonify({"success": True, **result})


@app.route("/admin/licenses/stats", methods=["GET"])
def admin_license_stats():
    return jsonify({"success": True, **storage.get_license_stats()})


# --- Stock ---

@app.route("/admin/stock", methods=["GET"])
def admin_get_stock():
    category = request.args.get("category", "")
    search = request.args.get("search", "")
    only_avail = request.args.get("available", "0") == "1"
    limit = int(request.args.get("limit", 1000))
    accounts = storage.get_stock_accounts(category, search, only_avail, limit)
    summary = storage.get_stock_summary()
    categories = storage.get_distinct_categories()
    return jsonify({
        "success": True,
        "accounts": accounts,
        "summary": summary,
        "categories": categories,
    })


@app.route("/admin/stock", methods=["POST"])
def admin_add_stock():
    data = request.get_json(silent=True) or {}
    category = (data.get("category") or "").strip()
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()
    if not category or not email or not password:
        return jsonify({"success": False, "error": "category, email, password required."}), 400
    result = storage.add_account(category, email, password)
    if result is None:
        return jsonify({"success": False, "error": "Duplicate entry."}), 409
    return jsonify({"success": True, **result})


@app.route("/admin/stock/bulk", methods=["POST"])
def admin_add_stock_bulk():
    data = request.get_json(silent=True) or {}
    category = (data.get("category") or "").strip()
    lines = (data.get("lines") or "").strip()
    if not category or not lines:
        return jsonify({"success": False, "error": "category and lines required."}), 400
    result = storage.add_accounts_bulk(category, lines)
    return jsonify({"success": True, **result})


@app.route("/admin/stock/<int:account_id>", methods=["DELETE"])
def admin_delete_stock_account(account_id: int):
    storage.delete_stock_account(account_id)
    return jsonify({"success": True})


@app.route("/admin/stock/clear", methods=["POST"])
def admin_clear_stock():
    data = request.get_json(silent=True) or {}
    category = (data.get("category") or "").strip()
    count = storage.clear_stock(category)
    return jsonify({"success": True, "deleted": count})


@app.route("/admin/stock/delete-used", methods=["POST"])
def admin_delete_used():
    count = storage.delete_used_stock()
    return jsonify({"success": True, "deleted": count})


@app.route("/admin/stock/dedup", methods=["POST"])
def admin_dedup_stock():
    result = storage.remove_duplicates()
    return jsonify({"success": True, **result})


@app.route("/admin/stock/export", methods=["GET"])
def admin_export_stock():
    category = request.args.get("category", "")
    data = storage.export_stock(category)
    return jsonify({"success": True, "data": data})


# --- Logs ---

@app.route("/admin/logs", methods=["GET"])
def admin_logs():
    return jsonify({
        "success": True,
        "admin_logs": storage.get_admin_logs(),
        "gen_logs": storage.get_gen_logs(),
    })


# --- Stats ---

@app.route("/admin/stats", methods=["GET"])
def admin_stats():
    stock = storage.get_stock_summary()
    lic = storage.get_license_stats()
    gen_count = storage.get_today_count("*") if False else 0
    # overall generation count today
    from storage import _connect
    conn = _connect()
    gen_today = conn.execute(
        "SELECT COUNT(*) FROM generation_log WHERE date(created_at) = date('now')"
    ).fetchone()[0]
    gen_total = conn.execute("SELECT COUNT(*) FROM generation_log").fetchone()[0]
    conn.close()

    return jsonify({
        "success": True,
        "licenses": lic,
        "stock": {
            "total": stock["total_accounts"],
            "available": stock["available_accounts"],
            "used": stock["used_accounts"],
        },
        "generations": {
            "today": gen_today,
            "total": gen_total,
        },
    })


# ---------------------------------------------------------------------------
# Health check (used by the app to verify the server is alive)
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Server runner
# ---------------------------------------------------------------------------

_server_port: int = 0


def get_server_port() -> int:
    return _server_port


def run_server(host: str = "127.0.0.1", preferred_port: int = 8099) -> int:
    """Start Flask in a daemon thread. Returns the actual port, or 0 on failure."""
    global _server_port

    import requests as _requests

    # Find an available port
    ports = [preferred_port] + list(range(preferred_port + 1, preferred_port + 10))
    chosen_port = 0
    for p in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((host, p))
            sock.close()
            chosen_port = p
            break
        except OSError:
            continue

    if chosen_port == 0:
        return 0

    _server_port = chosen_port

    t = threading.Thread(
        target=lambda: app.run(host=host, port=chosen_port, debug=False, use_reloader=False),
        daemon=True,
    )
    t.start()

    # Wait for server to actually be ready (health check poll)
    for _ in range(20):
        time.sleep(0.25)
        try:
            r = _requests.get(f"http://{host}:{chosen_port}/health", timeout=1)
            if r.status_code == 200:
                return chosen_port
        except Exception:
            continue

    # If we got here, the server never started
    _server_port = 0
    return 0
