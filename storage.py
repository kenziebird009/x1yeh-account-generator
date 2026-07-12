"""
Storage Module — SQLite backend for X1YEH Account Generator.
Licenses, stock, generation logs, admin logs.
"""

from __future__ import annotations

import sqlite3
import os
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


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS licenses (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key   TEXT UNIQUE NOT NULL,
            username      TEXT NOT NULL DEFAULT 'User',
            status        TEXT NOT NULL DEFAULT 'active',
            permissions   TEXT NOT NULL DEFAULT '[]',
            daily_limit   INTEGER NOT NULL DEFAULT 5,
            expiry_date   TEXT,
            max_uses       INTEGER DEFAULT NULL,
            times_used     INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS account_stock (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL COLLATE NOCASE,
            email    TEXT NOT NULL,
            password TEXT NOT NULL,
            used     INTEGER NOT NULL DEFAULT 0,
            used_by  TEXT,
            used_at  TEXT,
            added_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(category, email)
        );

        CREATE TABLE IF NOT EXISTS generation_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key  TEXT NOT NULL,
            category   TEXT NOT NULL,
            account_id INTEGER REFERENCES account_stock(id) ON DELETE SET NULL,
            email      TEXT,
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
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Generators / categories list
# ---------------------------------------------------------------------------

ALL_GENERATORS = ["Discord", "Steam", "Epic Games", "Fortnite", "Netflix", "VPN", "Rockstar", "Spotify"]


def get_all_categories() -> list[str]:
    return ALL_GENERATORS


# ---------------------------------------------------------------------------
# License Key Generation
# ---------------------------------------------------------------------------

def generate_license_key(length: int = 25) -> str:
    chars = string.ascii_uppercase + string.digits
    key = ''.join(secrets.choice(chars) for _ in range(length))
    if length == 25:
        key = f"{key[0:5]}-{key[5:10]}-{key[10:15]}-{key[15:20]}-{key[20:25]}"
    return key


# ---------------------------------------------------------------------------
# License Management
# ---------------------------------------------------------------------------

def create_license(
    username: str = "User",
    permissions: list[str] | None = None,
    daily_limit: int = 5,
    expiry_days: int | str | None = 365,
    max_uses: int | None = None,
    custom_expiry: str | None = None,
) -> dict:
    conn = _connect()
    key = generate_license_key()

    if permissions is None:
        permissions = []

    if custom_expiry:
        expiry = custom_expiry
    elif expiry_days == "lifetime" or expiry_days == 0 or expiry_days is None:
        expiry = None
    elif isinstance(expiry_days, str) and expiry_days.isdigit():
        expiry = (date.today() + timedelta(days=int(expiry_days))).isoformat()
    elif isinstance(expiry_days, int) and expiry_days > 0:
        expiry = (date.today() + timedelta(days=expiry_days)).isoformat()
    else:
        expiry = None

    conn.execute(
        """INSERT INTO licenses (license_key, username, permissions, daily_limit, expiry_date, max_uses)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (key, username, json_dumps(permissions), daily_limit, expiry, max_uses),
    )
    conn.execute(
        "INSERT INTO admin_log (action, detail) VALUES (?, ?)",
        ("create_license", f"Key {key[:10]}... for {username}"),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM licenses WHERE license_key = ?", (key,)).fetchone()
    conn.close()
    return _row_to_license_dict(row)


def list_licenses(search: str = "") -> list[dict]:
    conn = _connect()
    if search:
        rows = conn.execute(
            "SELECT * FROM licenses WHERE license_key LIKE ? OR username LIKE ? ORDER BY created_at DESC",
            (f"%{search}%", f"%{search}%"),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM licenses ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return [_row_to_license_dict(r) for r in rows]


def get_license(license_id: int = 0, license_key: str = "") -> dict | None:
    conn = _connect()
    if license_id:
        row = conn.execute("SELECT * FROM licenses WHERE id = ?", (license_id,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM licenses WHERE license_key = ?", (license_key,)).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_license_dict(row)


def update_license(
    license_id: int,
    username: str | None = None,
    permissions: list[str] | None = None,
    daily_limit: int | None = None,
    status: str | None = None,
    expiry_date: str | None = None,
    max_uses: int | None = None,
) -> dict | None:
    conn = _connect()
    builds = []
    params: list[Any] = []
    if username is not None:
        builds.append("username = ?")
        params.append(username)
    if permissions is not None:
        builds.append("permissions = ?")
        params.append(json_dumps(permissions))
    if daily_limit is not None:
        builds.append("daily_limit = ?")
        params.append(daily_limit)
    if status is not None:
        builds.append("status = ?")
        params.append(status)
    if expiry_date is not None:
        builds.append("expiry_date = ?")
        params.append(expiry_date)
    if max_uses is not None:
        builds.append("max_uses = ?")
        params.append(max_uses)
    if not builds:
        conn.close()
        return None
    builds.append("updated_at = datetime('now')")
    params.append(license_id)
    conn.execute(
        f"UPDATE licenses SET {', '.join(builds)} WHERE id = ?", params
    )
    conn.execute(
        "INSERT INTO admin_log (action, detail) VALUES ('update_license', ?)",
        (str(license_id),),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM licenses WHERE id = ?", (license_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_license_dict(row)


def delete_license(license_id: int) -> bool:
    conn = _connect()
    row = conn.execute("SELECT license_key FROM licenses WHERE id = ?", (license_id,)).fetchone()
    if row is None:
        conn.close()
        return False
    conn.execute("DELETE FROM licenses WHERE id = ?", (license_id,))
    conn.execute(
        "INSERT INTO admin_log (action, detail) VALUES ('delete_license', ?)",
        (row["license_key"][:20],),
    )
    conn.commit()
    conn.close()
    return True


def toggle_license_status(license_id: int) -> dict | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM licenses WHERE id = ?", (license_id,)).fetchone()
    if row is None:
        conn.close()
        return None
    new_status = "disabled" if row["status"] == "active" else "active"
    conn.execute("UPDATE licenses SET status = ?, updated_at = datetime('now') WHERE id = ?", (new_status, license_id))
    conn.commit()
    row2 = conn.execute("SELECT * FROM licenses WHERE id = ?", (license_id,)).fetchone()
    conn.close()
    return _row_to_license_dict(row2)


def validate_license(license_key: str) -> dict | None:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM licenses WHERE license_key = ?", (license_key,)
    ).fetchone()
    if row is None:
        conn.close()
        return None
    if row["status"] != "active":
        conn.close()
        return None
    if row["expiry_date"]:
        try:
            exp = date.fromisoformat(row["expiry_date"])
            if exp < date.today():
                conn.execute("UPDATE licenses SET status = 'expired' WHERE id = ?", (row["id"],))
                conn.commit()
                conn.close()
                return None
        except ValueError:
            pass
    if row["max_uses"] is not None and row["times_used"] >= row["max_uses"]:
        conn.close()
        return None
    token = secrets.token_hex(16)
    conn.close()
    return {
        "token": token,
        "license_key": license_key,
        "username": row["username"],
        "permissions": json_loads(row["permissions"]),
        "daily_limit": row["daily_limit"],
        "expiry_date": row["expiry_date"],
        "status": row["status"],
        "max_uses": row["max_uses"],
        "times_used": row["times_used"],
    }


def get_license_stats() -> dict:
    conn = _connect()
    total = conn.execute("SELECT COUNT(*) FROM licenses").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM licenses WHERE status = 'active'").fetchone()[0]
    disabled = conn.execute("SELECT COUNT(*) FROM licenses WHERE status = 'disabled'").fetchone()[0]
    expired = conn.execute("SELECT COUNT(*) FROM licenses WHERE status = 'expired'").fetchone()[0]
    conn.close()
    return {"total": total, "active": active, "disabled": disabled, "expired": expired}


# ---------------------------------------------------------------------------
# Account Stock
# ---------------------------------------------------------------------------

def add_account(category: str, email: str, password: str) -> dict | None:
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO account_stock (category, email, password) VALUES (?, ?, ?)",
            (category.strip(), email.strip(), password.strip()),
        )
        conn.commit()
        if cur.lastrowid == 0:
            conn.close()
            return None  # duplicate
        conn.close()
        return {"id": cur.lastrowid, "category": category, "email": email}
    except sqlite3.IntegrityError:
        conn.close()
        return None


def add_accounts_bulk(category: str, lines: str) -> dict:
    conn = _connect()
    added = 0
    duplicates = 0
    for line in lines.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split(":", 1)
        if len(parts) != 2:
            continue
        email, password = parts[0].strip(), parts[1].strip()
        if not email or not password:
            continue
        try:
            cur = conn.execute(
                "INSERT OR IGNORE INTO account_stock (category, email, password) VALUES (?, ?, ?)",
                (category.strip(), email.strip(), password),
            )
            if cur.lastrowid > 0:
                added += 1
            else:
                duplicates += 1
        except Exception:
            duplicates += 1
    conn.commit()
    conn.execute(
        "INSERT INTO admin_log (action, detail) VALUES (?, ?)",
        ("bulk_stock", f"{category}: added {added}, dup {duplicates}"),
    )
    conn.close()
    return {"added": added, "duplicates": duplicates, "category": category}


def get_stock_summary() -> dict:
    conn = _connect()
    total = conn.execute("SELECT COUNT(*) FROM account_stock").fetchone()[0]
    used = conn.execute("SELECT COUNT(*) FROM account_stock WHERE used = 1").fetchone()[0]
    available = total - used
    generated_today = conn.execute(
        "SELECT COUNT(*) FROM generation_log WHERE date(created_at) = date('now') AND success = 1"
    ).fetchone()[0]
    cat_rows = conn.execute(
        "SELECT category, COUNT(*) as total, SUM(CASE WHEN used = 0 THEN 1 ELSE 0 END) as unused "
        "FROM account_stock GROUP BY category ORDER BY category"
    ).fetchall()
    conn.close()
    cats = {}
    for r in cat_rows:
        cats[r["category"]] = {
            "total": r["total"],
            "used": r["total"] - r["unused"],
            "remaining": r["unused"],
        }
    return {
        "available_accounts": available,
        "total_accounts": total,
        "used_accounts": used,
        "generated_today": generated_today,
        "categories": cats,
    }


def get_stock_accounts(category: str = "", search: str = "", only_available: bool = False, limit: int = 1000) -> list[dict]:
    conn = _connect()
    query = "SELECT * FROM account_stock WHERE 1=1"
    params: list[Any] = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND (email LIKE ? OR password LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if only_available:
        query += " AND used = 0"
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_stock_row_to_dict(r) for r in rows]


def delete_stock_account(account_id: int) -> bool:
    conn = _connect()
    conn.execute("UPDATE generation_log SET account_id = NULL WHERE account_id = ?", (account_id,))
    conn.execute("DELETE FROM account_stock WHERE id = ?", (account_id,))
    conn.commit()
    conn.close()
    return True


def clear_stock(category: str = "") -> int:
    conn = _connect()
    # Null out references in generation_log first to avoid FK errors
    if category:
        conn.execute(
            "UPDATE generation_log SET account_id = NULL WHERE account_id IN "
            "(SELECT id FROM account_stock WHERE category = ?)", (category,)
        )
        cur = conn.execute("DELETE FROM account_stock WHERE category = ?", (category,))
    else:
        conn.execute("UPDATE generation_log SET account_id = NULL")
        cur = conn.execute("DELETE FROM account_stock")
    conn.commit()
    conn.close()
    return cur.rowcount


def delete_used_stock() -> int:
    conn = _connect()
    conn.execute("UPDATE generation_log SET account_id = NULL WHERE account_id IN (SELECT id FROM account_stock WHERE used = 1)")
    cur = conn.execute("DELETE FROM account_stock WHERE used = 1")
    conn.commit()
    conn.close()
    return cur.rowcount


def export_stock(category: str = "") -> str:
    conn = _connect()
    if category:
        rows = conn.execute("SELECT email, password FROM account_stock WHERE category = ? AND used = 0 ORDER BY id", (category,)).fetchall()
    else:
        rows = conn.execute("SELECT category, email, password FROM account_stock WHERE used = 0 ORDER BY category, id").fetchall()
    conn.close()
    lines = []
    for r in rows:
        if category:
            lines.append(f"{r['email']}:{r['password']}")
        else:
            lines.append(f"[{r['category']}] {r['email']}:{r['password']}")
    return "\n".join(lines)


def remove_duplicates() -> dict:
    conn = _connect()
    conn.execute(
        "UPDATE generation_log SET account_id = NULL WHERE account_id IN "
        "(SELECT id FROM account_stock WHERE id NOT IN (SELECT MIN(id) FROM account_stock GROUP BY category, email))"
    )
    cur = conn.execute(
        "DELETE FROM account_stock WHERE id NOT IN (SELECT MIN(id) FROM account_stock GROUP BY category, email)"
    )
    conn.commit()
    removed = cur.rowcount
    conn.close()
    return {"removed": removed}


def get_distinct_categories() -> list[str]:
    conn = _connect()
    rows = conn.execute("SELECT DISTINCT category FROM account_stock ORDER BY category").fetchall()
    conn.close()
    return [r["category"] for r in rows]


# ---------------------------------------------------------------------------
# Account Generation
# ---------------------------------------------------------------------------

def get_today_count(license_key: str) -> int:
    conn = _connect()
    count = conn.execute(
        "SELECT COUNT(*) FROM generation_log WHERE license_key = ? AND date(created_at) = date('now') AND success = 1",
        (license_key,),
    ).fetchone()[0]
    conn.close()
    return count


def generate_account(license_key: str, category: str, daily_limit: int) -> dict:
    conn = _connect()

    today_count = conn.execute(
        "SELECT COUNT(*) FROM generation_log WHERE license_key = ? AND date(created_at) = date('now') AND success = 1",
        (license_key,),
    ).fetchone()[0]

    if today_count >= daily_limit:
        conn.close()
        return {"success": False, "error": f"Daily limit reached ({daily_limit}/day)."}

    row = conn.execute(
        "SELECT id, email, password FROM account_stock WHERE category = ? AND used = 0 ORDER BY id LIMIT 1",
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
        "UPDATE licenses SET times_used = times_used + 1 WHERE license_key = ?",
        (license_key,),
    )
    conn.execute(
        "INSERT INTO generation_log (license_key, category, account_id, email, success) VALUES (?, ?, ?, ?, 1)",
        (license_key, category, row["id"], row["email"]),
    )
    conn.commit()
    conn.close()

    return {
        "success": True,
        "account": {"email": row["email"], "password": row["password"], "category": category},
        "remaining_today": daily_limit - today_count - 1,
    }


# ---------------------------------------------------------------------------
# Profile / Dashboard
# ---------------------------------------------------------------------------

def get_profile(license_key: str) -> dict:
    conn = _connect()
    row = conn.execute("SELECT * FROM licenses WHERE license_key = ?", (license_key,)).fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "License not found."}

    today_gen = conn.execute(
        "SELECT COUNT(*) FROM generation_log WHERE license_key = ? AND date(created_at) = date('now') AND success = 1",
        (license_key,),
    ).fetchone()[0]
    total_gen = conn.execute(
        "SELECT COUNT(*) FROM generation_log WHERE license_key = ? AND success = 1",
        (license_key,),
    ).fetchone()[0]
    recent = conn.execute(
        "SELECT category, email, created_at, success FROM generation_log WHERE license_key = ? ORDER BY created_at DESC LIMIT 8",
        (license_key,),
    ).fetchall()
    conn.close()

    activity = []
    for r in recent:
        action_text = f"Generated {r['category']}" if r["success"] else f"Failed {r['category']}"
        if r["email"]:
            action_text += f" ({r['email']})"
        activity.append({"description": action_text, "timestamp": r["created_at"]})

    return {
        "success": True,
        "license_status": row["status"].capitalize(),
        "username": row["username"],
        "expiry_date": row["expiry_date"] or "Never",
        "daily_limit": row["daily_limit"],
        "version": "1.0.0",
        "server": "X1YEH Local",
        "account_stats": {
            "generated_today": today_gen,
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
    rows = conn.execute("SELECT * FROM admin_log ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_gen_logs(limit: int = 200) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT gl.*, lic.username FROM generation_log gl LEFT JOIN licenses lic ON gl.license_key = lic.license_key "
        "ORDER BY gl.created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Seed default data
# ---------------------------------------------------------------------------

def seed_default_data() -> None:
    conn = _connect()
    existing = conn.execute("SELECT COUNT(*) FROM licenses").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    conn.execute(
        "INSERT INTO licenses (license_key, username, status, permissions, daily_limit, max_uses) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            "ADMIN-DEFAULT-KEY",
            "Admin",
            "active",
            json_dumps(ALL_GENERATORS),
            999,
            None,
        ),
    )

    demo_stock = [
        ("Discord", "discord_nitro1@stock.com", "nitro_pass_101"),
        ("Discord", "discord_user2@stock.com", "dsc_pass_202"),
        ("Discord", "discord_mod@stock.com", "mod_pass_303"),
        ("Steam", "steam_gamer99@stock.com", "steam99_pass"),
        ("Steam", "steam_trader@stock.com", "trade_404"),
        ("Steam", "steam_csgo@stock.com", "csgo_505"),
        ("Epic Games", "epic_fortnite@stock.com", "epic_fort_111"),
        ("Epic Games", "epic_gamer@stock.com", "epic_222"),
        ("Fortnite", "fn_skins@stock.com", "fn_skins_333"),
        ("Fortnite", "fn_og@stock.com", "fn_og_444"),
        ("Netflix", "netflix_4k@stock.com", "nf_4k_555"),
        ("Netflix", "netflix_share@stock.com", "nf_share_666"),
        ("Netflix", "netflix_prem@stock.com", "nf_prem_777"),
        ("VPN", "vpn_express@stock.com", "vpn_pass_888"),
        ("VPN", "vpn_nord@stock.com", "nord_999"),
        ("Rockstar", "rockstar_gta@stock.com", "gta6_000"),
        ("Rockstar", "rockstar_rdr@stock.com", "rdr2_111"),
        ("Spotify", "spotify_prem@stock.com", "spot_prem_222"),
        ("Spotify", "spotify_fam@stock.com", "spot_fam_333"),
    ]
    for cat, email, pw in demo_stock:
        conn.execute(
            "INSERT INTO account_stock (category, email, password) VALUES (?, ?, ?)",
            (cat, email, pw),
        )

    conn.execute(
        "INSERT INTO admin_log (action, detail) VALUES ('seed', 'Seeded admin key and demo stock')"
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


def _row_to_license_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "license_key": row["license_key"],
        "username": row["username"],
        "status": row["status"],
        "permissions": json_loads(row["permissions"]),
        "daily_limit": row["daily_limit"],
        "expiry_date": row["expiry_date"],
        "max_uses": row["max_uses"],
        "times_used": row["times_used"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _stock_row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "category": row["category"],
        "email": row["email"],
        "password": row["password"],
        "used": bool(row["used"]),
        "used_by": row["used_by"],
        "used_at": row["used_at"],
        "added_at": row["added_at"],
    }
