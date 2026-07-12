"""
Storage Module
SQLite-backed local storage for licenses, accounts, stock, and generation logs.
"""

from __future__ import annotations

import sqlite3
import os
import uuid
import hashlib
import secrets
import string
from datetime import datetime, date, timedelta
from typing import Any


DB_PATH: str | None = None


def _get_db_path() -> str:
    global DB_PATH
    if DB_PATH:
        return DB_PATH
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    folder = os.path.join(base, "X1YEH_AccountGen")
    os.makedirs(folder, exist_ok=True)
    DB_PATH = os.path.join(folder, "data.db")
    return DB_PATH


def set_db_path(path: str) -> None:
    global DB_PATH
    DB_PATH = path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db() -> None:
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS licenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            username    TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'active',
            permissions TEXT NOT NULL DEFAULT '[]',
            daily_limit INTEGER NOT NULL DEFAULT 5,
            expiry_date TEXT,
            hwid        TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            last_used   TEXT
        );

        CREATE TABLE IF NOT EXISTS account_stock (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            email    TEXT NOT NULL,
            password TEXT NOT NULL,
            used     INTEGER NOT NULL DEFAULT 0,
            used_by  TEXT,
            used_at  TEXT,
            added_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS generation_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            license    TEXT NOT NULL,
            category   TEXT NOT NULL,
            account_id INTEGER,
            success    INTEGER NOT NULL DEFAULT 1,
            error_msg  TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS admin_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            action     TEXT NOT NULL,
            detail     TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# License Management
# ---------------------------------------------------------------------------

def _generate_license_key() -> str:
    chars = string.ascii_uppercase + string.digits
    block = lambda n: ''.join(secrets.choice(chars) for _ in range(n))
    return f"{block(5)}-{block(5)}-{block(5)}-{block(5)}-{block(5)}"


def create_license(
    username: str,
    permissions: list[str],
    daily_limit: int = 5,
    expiry_days: int = 365,
    hwid: str | None = None,
) -> dict:
    conn = _connect()
    key = _generate_license_key()
    expiry = (date.today() + timedelta(days=expiry_days)).isoformat() if expiry_days > 0 else None
    conn.execute(
        "INSERT INTO licenses (license_key, username, permissions, daily_limit, expiry_date, hwid) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (key, username, json_dumps(permissions), daily_limit, expiry, hwid),
    )
    conn.execute(
        "INSERT INTO admin_log (action, detail) VALUES (?, ?)",
        ("create_license", f"Created key {key[:10]}... for {username}"),
    )
    conn.commit()
    conn.close()
    return {"license_key": key, "username": username, "permissions": permissions, "daily_limit": daily_limit}


def list_licenses() -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, license_key, username, status, permissions, daily_limit, expiry_date, created_at, last_used "
        "FROM licenses ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "license_key": r["license_key"],
            "username": r["username"],
            "status": r["status"],
            "permissions": json_loads(r["permissions"]),
            "daily_limit": r["daily_limit"],
            "expiry_date": r["expiry_date"],
            "created_at": r["created_at"],
            "last_used": r["last_used"],
        })
    return result


def delete_license(license_id: int) -> bool:
    conn = _connect()
    conn.execute("DELETE FROM licenses WHERE id = ?", (license_id,))
    conn.execute("INSERT INTO admin_log (action, detail) VALUES ('delete_license', ?)", (str(license_id),))
    conn.commit()
    conn.close()
    return True


def revoke_license(license_key: str) -> bool:
    conn = _connect()
    conn.execute("UPDATE licenses SET status = 'revoked' WHERE license_key = ?", (license_key,))
    conn.commit()
    conn.close()
    return True


def validate_license(license_key: str, hwid: str | None = None) -> dict | None:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM licenses WHERE license_key = ? AND status = 'active'", (license_key,)
    ).fetchone()
    if row is None:
        conn.close()
        return None
    if row["expiry_date"]:
        exp = date.fromisoformat(row["expiry_date"])
        if exp < date.today():
            conn.execute("UPDATE licenses SET status = 'expired' WHERE license_key = ?", (license_key,))
            conn.commit()
            conn.close()
            return None
    if row["hwid"] is not None and row["hwid"] != hwid:
        conn.close()
        return None
    conn.execute("UPDATE licenses SET last_used = datetime('now') WHERE license_key = ?", (license_key,))
    conn.commit()
    conn.close()
    # generate a simple token
    token = hashlib.sha256((license_key + str(uuid.uuid4())).encode()).hexdigest()[:32]
    return {
        "token": token,
        "license_key": license_key,
        "username": row["username"],
        "permissions": json_loads(row["permissions"]),
        "daily_limit": row["daily_limit"],
        "expiry_date": row["expiry_date"],
        "status": row["status"],
    }


# ---------------------------------------------------------------------------
# Account Stock
# ---------------------------------------------------------------------------

def add_account(category: str, email: str, password: str) -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO account_stock (category, email, password) VALUES (?, ?, ?)",
        (category, email, password),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def add_accounts_bulk(entries: list[tuple[str, str, str]]) -> int:
    conn = _connect()
    count = 0
    for cat, email, pw in entries:
        conn.execute(
            "INSERT INTO account_stock (category, email, password) VALUES (?, ?, ?)",
            (cat, email, pw),
        )
        count += 1
    conn.commit()
    conn.close()
    return count


def get_stock() -> dict:
    conn = _connect()
    available = conn.execute(
        "SELECT COUNT(*) FROM account_stock WHERE used = 0"
    ).fetchone()[0]
    generated_today = conn.execute(
        "SELECT COUNT(*) FROM generation_log WHERE date(created_at) = date('now') AND success = 1"
    ).fetchone()[0]
    categories = conn.execute(
        "SELECT category, COUNT(*) as total, "
        "SUM(CASE WHEN used = 0 THEN 1 ELSE 0 END) as unused "
        "FROM account_stock GROUP BY category"
    ).fetchall()
    conn.close()

    cat_data = {}
    for r in categories:
        cat_data[r["category"]] = {
            "total": r["total"],
            "used": r["total"] - r["unused"],
            "remaining": r["unused"],
        }

    return {
        "available_accounts": available,
        "generated_today": generated_today,
        "remaining": available,
        "categories": cat_data,
    }


def get_accounts_by_category(category: str) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, category, email, password, used, used_by, used_at "
        "FROM account_stock WHERE category = ? ORDER BY id",
        (category,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Account Generation
# ---------------------------------------------------------------------------

def get_today_count(license_key: str) -> int:
    conn = _connect()
    count = conn.execute(
        "SELECT COUNT(*) FROM generation_log "
        "WHERE license = ? AND date(created_at) = date('now') AND success = 1",
        (license_key,),
    ).fetchone()[0]
    conn.close()
    return count


def generate_account(license_key: str, category: str, daily_limit: int) -> dict:
    conn = _connect()

    today_count = conn.execute(
        "SELECT COUNT(*) FROM generation_log "
        "WHERE license = ? AND date(created_at) = date('now') AND success = 1",
        (license_key,),
    ).fetchone()[0]

    if today_count >= daily_limit:
        conn.close()
        return {"success": False, "error": f"Daily limit reached ({daily_limit}/day). Try again tomorrow."}

    row = conn.execute(
        "SELECT id, email, password FROM account_stock "
        "WHERE category = ? AND used = 0 ORDER BY id LIMIT 1",
        (category,),
    ).fetchone()

    if row is None:
        conn.close()
        return {"success": False, "error": f"No accounts available in '{category}'."}

    conn.execute(
        "UPDATE account_stock SET used = 1, used_by = ?, used_at = datetime('now') WHERE id = ?",
        (license_key, row["id"]),
    )
    conn.execute(
        "INSERT INTO generation_log (license, category, account_id, success) VALUES (?, ?, ?, 1)",
        (license_key, category, row["id"]),
    )
    conn.commit()
    conn.close()

    return {
        "success": True,
        "account": {
            "email": row["email"],
            "password": row["password"],
            "category": category,
        },
        "remaining_today": daily_limit - today_count - 1,
    }


# ---------------------------------------------------------------------------
# Profile / Dashboard Data
# ---------------------------------------------------------------------------

def get_profile(license_key: str) -> dict:
    conn = _connect()
    row = conn.execute("SELECT * FROM licenses WHERE license_key = ?", (license_key,)).fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "License not found."}

    today_count = conn.execute(
        "SELECT COUNT(*) FROM generation_log "
        "WHERE license = ? AND date(created_at) = date('now') AND success = 1",
        (license_key,),
    ).fetchone()[0]

    total_gen = conn.execute(
        "SELECT COUNT(*) FROM generation_log WHERE license = ? AND success = 1", (license_key,)
    ).fetchone()[0]

    recent = conn.execute(
        "SELECT category, created_at, success FROM generation_log "
        "WHERE license = ? ORDER BY created_at DESC LIMIT 8",
        (license_key,),
    ).fetchall()

    conn.close()

    activity = []
    for r in recent:
        activity.append({
            "description": f"{'Generated' if r['success'] else 'Failed'} {r['category']}",
            "timestamp": r["created_at"],
        })

    return {
        "success": True,
        "license_status": row["status"].capitalize(),
        "username": row["username"],
        "expiry_date": row["expiry_date"] or "Never",
        "version": "1.0.0",
        "server": "X1YEH Local",
        "account_stats": {
            "generated_today": today_count,
            "total_generated": total_gen,
            "categories": len(json_loads(row["permissions"])),
        },
        "recent_activity": activity,
    }


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

def get_admin_logs(limit: int = 50) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM admin_log ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_gen_logs(limit: int = 100) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM generation_log ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Admin Settings
# ---------------------------------------------------------------------------

def get_setting(key: str, default: str = "") -> str:
    conn = _connect()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj)


def json_loads(s: str) -> Any:
    import json
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return []


# ---------------------------------------------------------------------------
# Seed default data
# ---------------------------------------------------------------------------

def seed_default_data() -> None:
    conn = _connect()
    existing = conn.execute("SELECT COUNT(*) FROM licenses WHERE license_key = 'ADMIN-DEFAULT-KEY'").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    # Default admin license
    conn.execute(
        "INSERT INTO licenses (license_key, username, status, permissions, daily_limit) "
        "VALUES (?, ?, ?, ?, ?)",
        ("ADMIN-DEFAULT-KEY", "Admin", "active", json_dumps(["VPN", "Netflix", "Steam", "Discord", "Rockstar"]), 999),
    )

    # Demo accounts
    demo_accounts = [
        ("VPN", "demo_vpn@x1yeh.com", "vpn_pass_123"),
        ("VPN", "vpn_user2@x1yeh.com", "secure_vpn_456"),
        ("VPN", "vpn_premium@x1yeh.com", "prem_vpn_789"),
        ("Netflix", "netflix_demo@x1yeh.com", "nf_pass_111"),
        ("Netflix", "netflix_4k@x1yeh.com", "nf_4k_222"),
        ("Steam", "steam_acc@x1yeh.com", "steam_pass_333"),
        ("Steam", "steam_gamer@x1yeh.com", "gamer_444"),
        ("Discord", "discord_nitro@x1yeh.com", "nitro_555"),
        ("Rockstar", "rockstar_gtav@x1yeh.com", "rstar_666"),
        ("Rockstar", "rockstar_r2d2@x1yeh.com", "rstar_777"),
    ]
    conn.executemany(
        "INSERT INTO account_stock (category, email, password) VALUES (?, ?, ?)",
        demo_accounts,
    )

    conn.execute(
        "INSERT INTO admin_log (action, detail) VALUES ('seed', 'Seeded default licenses and demo accounts')"
    )
    conn.commit()
    conn.close()
