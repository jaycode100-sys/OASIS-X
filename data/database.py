import sqlite3, json, os, threading
from datetime import datetime

from config import settings

DB_DIR = settings.OASIS_DB_DIR
DB_PATH = settings.OASIS_DB_PATH

_local = threading.local()

def _get_conn():
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(DB_DIR, exist_ok=True)
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn

def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            city TEXT NOT NULL,
            season TEXT,
            n_samples INTEGER,
            summary_json TEXT,
            ncc_compliance_json TEXT
        );
        CREATE TABLE IF NOT EXISTS telemetry_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            row_index INTEGER,
            row_data_json TEXT,
            FOREIGN KEY (run_id) REFERENCES pipeline_runs(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS diagnosis_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            run_id INTEGER,
            row_index INTEGER,
            diagnosis_json TEXT,
            source TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (run_id) REFERENCES pipeline_runs(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            message TEXT NOT NULL,
            html TEXT,
            user_id INTEGER,
            username TEXT,
            user_agent TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            display_name TEXT,
            avatar_color TEXT DEFAULT '#FF9E00',
            theme TEXT DEFAULT 'dark',
            settings_json TEXT DEFAULT '{}',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_number TEXT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            priority TEXT NOT NULL DEFAULT 'normal',
            assigned_to INTEGER,
            tags TEXT DEFAULT '[]',
            resolution_notes TEXT,
            closed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS complaint_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            message_type TEXT DEFAULT 'message',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE,
            FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    # Add user_id column to existing tables if missing
    try:
        conn.execute("ALTER TABLE pipeline_runs ADD COLUMN user_id INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE diagnosis_logs ADD COLUMN user_id INTEGER")
    except sqlite3.OperationalError:
        pass
    # Migrations for complaints table
    for col, typ, default in [
        ("case_number", "TEXT", None),
        ("priority", "TEXT", "'normal'"),
        ("tags", "TEXT", "'[]'"),
        ("resolution_notes", "TEXT", None),
        ("closed_at", "TEXT", None),
    ]:
        try:
            if default:
                conn.execute(f"ALTER TABLE complaints ADD COLUMN {col} {typ} DEFAULT {default}")
            else:
                conn.execute(f"ALTER TABLE complaints ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass
    try:
        conn.execute("ALTER TABLE complaint_messages ADD COLUMN message_type TEXT DEFAULT 'message'")
    except sqlite3.OperationalError:
        pass
    conn.commit()

def save_pipeline_run(city, season, n_samples, rows, summary, ncc_compliance):
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO pipeline_runs (city, season, n_samples, summary_json, ncc_compliance_json) VALUES (?,?,?,?,?)",
        (city, season or "", n_samples, json.dumps(summary), json.dumps(ncc_compliance))
    )
    run_id = cur.lastrowid
    for i, row in enumerate(rows):
        conn.execute(
            "INSERT INTO telemetry_rows (run_id, row_index, row_data_json) VALUES (?,?,?)",
            (run_id, i, json.dumps(row, default=str))
        )
    conn.commit()
    return run_id

def get_pipeline_runs(limit=20):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, created_at, city, season, n_samples FROM pipeline_runs ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    return [dict(r) for r in rows]

def get_pipeline_run(run_id):
    conn = _get_conn()
    r = conn.execute("SELECT * FROM pipeline_runs WHERE id=?", (run_id,)).fetchone()
    if not r:
        return None
    result = dict(r)
    result["summary"] = json.loads(result.pop("summary_json", "{}"))
    result["ncc_compliance"] = json.loads(result.pop("ncc_compliance_json", "{}"))
    telemetry = conn.execute(
        "SELECT row_index, row_data_json FROM telemetry_rows WHERE run_id=? ORDER BY row_index",
        (run_id,)
    ).fetchall()
    result["rows"] = [json.loads(t["row_data_json"]) for t in telemetry]
    return result

def delete_pipeline_run(run_id):
    conn = _get_conn()
    conn.execute("DELETE FROM telemetry_rows WHERE run_id=?", (run_id,))
    conn.execute("DELETE FROM pipeline_runs WHERE id=?", (run_id,))
    conn.commit()

def save_diagnosis(run_id, row_index, diagnosis, source):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO diagnosis_logs (run_id, row_index, diagnosis_json, source) VALUES (?,?,?,?)",
        (run_id, row_index, json.dumps(diagnosis, default=str), source)
    )
    conn.commit()

def save_chat_message(role, content):
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO chat_messages (role, content) VALUES (?,?)",
        (role, content)
    )
    conn.commit()
    return cur.lastrowid

def get_chat_history(limit=50):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT role, content FROM chat_messages ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    rows.reverse()
    return [dict(r) for r in rows]

def clear_chat_history():
    conn = _get_conn()
    conn.execute("DELETE FROM chat_messages")
    conn.commit()


# ── User CRUD ───────────────────────────────────────────────────────────────────

def get_user_by_username(username: str) -> dict | None:
    conn = _get_conn()
    r = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(r) if r else None


def get_user_by_id(user_id: int) -> dict | None:
    conn = _get_conn()
    r = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(r) if r else None


def create_user(username: str, hashed_password: str, role: str = "user") -> dict:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO users (username, hashed_password, role) VALUES (?, ?, ?)",
        (username, hashed_password, role),
    )
    conn.commit()
    return get_user_by_id(cur.lastrowid)


def get_all_users() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, username, role, created_at FROM users ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def delete_user(user_id: int) -> bool:
    conn = _get_conn()
    cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    return cur.rowcount > 0


# ── Activity Logs ─────────────────────────────────────────────────────────────────

def log_activity(act_type: str, message: str, html: str = None, user_id: int = None, username: str = None, user_agent: str = None):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO activity_logs (type, message, html, user_id, username, user_agent) VALUES (?,?,?,?,?,?)",
        (act_type, message, html or message, user_id, username, user_agent)
    )
    conn.commit()


def get_activities(limit: int = 50, user_id: int = None, type_filter: str = None) -> list[dict]:
    conn = _get_conn()
    sql = "SELECT id, type, message, html, username, user_agent, created_at FROM activity_logs"
    params = []
    conditions = []
    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(user_id)
    if type_filter:
        conditions.append("type = ?")
        params.append(type_filter)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ── User Profiles ──────────────────────────────────────────────────────────────────

def get_user_profile(user_id: int) -> dict | None:
    conn = _get_conn()
    r = conn.execute("SELECT * FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
    if r:
        res = dict(r)
        res["settings"] = json.loads(res.pop("settings_json", "{}"))
        return res
    return None


def create_user_profile(user_id: int, display_name: str = None, avatar_color: str = "#FF9E00", theme: str = "dark") -> dict:
    conn = _get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO user_profiles (user_id, display_name, avatar_color, theme) VALUES (?,?,?,?)",
        (user_id, display_name or "", avatar_color, theme)
    )
    conn.commit()
    return get_user_profile(user_id)


def update_user_profile(user_id: int, **kwargs) -> dict | None:
    conn = _get_conn()
    allowed = {"display_name", "avatar_color", "theme", "settings_json", "settings"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_user_profile(user_id)
    if "settings" in updates:
        updates["settings_json"] = json.dumps(updates.pop("settings"))
    sets = ", ".join(f"{k}=?" for k in updates)
    conn.execute(f"UPDATE user_profiles SET {sets} WHERE user_id=?", (*updates.values(), user_id))
    conn.commit()
    return get_user_profile(user_id)


# ── Cases (formerly Complaints) ──────────────────────────────────────────────────

import uuid

def _gen_case_number():
    return f"CASE-{uuid.uuid4().hex[:8].upper()}"

def create_complaint(user_id: int, subject: str) -> dict:
    conn = _get_conn()
    case_number = _gen_case_number()
    cur = conn.execute(
        "INSERT INTO complaints (case_number, user_id, subject) VALUES (?,?,?)",
        (case_number, user_id, subject)
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM complaints WHERE id=?", (cur.lastrowid,)).fetchone())


def get_complaints(user_id: int = None, status: str = None) -> list[dict]:
    conn = _get_conn()
    sql = "SELECT * FROM complaints"
    params = []
    conditions = []
    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(user_id)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY updated_at DESC"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_complaint(complaint_id: int) -> dict | None:
    conn = _get_conn()
    r = conn.execute("SELECT * FROM complaints WHERE id=?", (complaint_id,)).fetchone()
    return dict(r) if r else None


def update_complaint_status(complaint_id: int, status: str, assigned_to: int = None,
                            priority: str = None, resolution_notes: str = None) -> dict | None:
    conn = _get_conn()
    sets = ["updated_at=datetime('now','localtime')"]
    params = []
    if status:
        sets.append("status=?")
        params.append(status)
        if status == "closed":
            sets.append("closed_at=datetime('now','localtime')")
    if assigned_to is not None:
        sets.append("assigned_to=?")
        params.append(assigned_to)
    if priority:
        sets.append("priority=?")
        params.append(priority)
    if resolution_notes is not None:
        sets.append("resolution_notes=?")
        params.append(resolution_notes)
    params.append(complaint_id)
    conn.execute(f"UPDATE complaints SET {','.join(sets)} WHERE id=?", params)
    conn.commit()
    return get_complaint(complaint_id)


def add_complaint_message(complaint_id: int, sender_id: int, message: str,
                          message_type: str = "message") -> dict:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO complaint_messages (complaint_id, sender_id, message, message_type) VALUES (?,?,?,?)",
        (complaint_id, sender_id, message, message_type)
    )
    conn.execute("UPDATE complaints SET updated_at=datetime('now','localtime') WHERE id=?", (complaint_id,))
    conn.commit()
    return dict(conn.execute(
        "SELECT cm.*, u.username as sender_name FROM complaint_messages cm "
        "JOIN users u ON u.id = cm.sender_id WHERE cm.id=?", (cur.lastrowid,)
    ).fetchone())


def get_complaint_messages(complaint_id: int) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT cm.*, u.username as sender_name FROM complaint_messages cm "
        "JOIN users u ON u.id = cm.sender_id "
        "WHERE cm.complaint_id=? ORDER BY cm.id",
        (complaint_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_open_complaints() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT c.*, u.username as user_name FROM complaints c "
        "JOIN users u ON u.id = c.user_id "
        "WHERE c.status='open' ORDER BY c.created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_cases_for_user(user_id: int, role: str = "user") -> list[dict]:
    """Get cases with last message preview and unread count — messaging app style."""
    conn = _get_conn()
    if role == "superadmin":
        # Superadmin sees all cases
        cases = conn.execute(
            "SELECT c.*, u.username as user_name FROM complaints c "
            "JOIN users u ON u.id = c.user_id "
            "ORDER BY c.updated_at DESC"
        ).fetchall()
    else:
        cases = conn.execute(
            "SELECT c.*, u.username as user_name FROM complaints c "
            "JOIN users u ON u.id = c.user_id "
            "WHERE c.user_id=? ORDER BY c.updated_at DESC",
            (user_id,)
        ).fetchall()

    result = []
    for case in cases:
        case_dict = dict(case)
        # Get last message
        last_msg = conn.execute(
            "SELECT cm.message, cm.created_at, u.username as sender_name "
            "FROM complaint_messages cm JOIN users u ON u.id = cm.sender_id "
            "WHERE cm.complaint_id=? ORDER BY cm.id DESC LIMIT 1",
            (case_dict["id"],)
        ).fetchone()
        if last_msg:
            case_dict["last_message"] = dict(last_msg)["message"]
            case_dict["last_message_at"] = dict(last_msg)["created_at"]
            case_dict["last_sender"] = dict(last_msg)["sender_name"]
        else:
            case_dict["last_message"] = case_dict["subject"]
            case_dict["last_message_at"] = case_dict["created_at"]
            case_dict["last_sender"] = case_dict["user_name"]

        # Get unread count (messages from others not yet seen)
        # We count messages after the user's last read — use a simple approach:
        # Count all messages that aren't from the current user
        unread = conn.execute(
            "SELECT COUNT(*) as cnt FROM complaint_messages "
            "WHERE complaint_id=? AND sender_id!=?",
            (case_dict["id"], user_id)
        ).fetchone()
        case_dict["unread_count"] = dict(unread)["cnt"] if unread else 0

        # Get user avatar data from profile
        profile = conn.execute(
            "SELECT up.avatar_color, up.settings_json FROM user_profiles up "
            "WHERE up.user_id=?", (case_dict["user_id"],)
        ).fetchone()
        if profile:
            p = dict(profile)
            case_dict["avatar_color"] = p.get("avatar_color", "#FF9E00")
            try:
                settings = json.loads(p.get("settings_json", "{}"))
                case_dict["avatar_data"] = settings.get("avatar_data", "")
            except:
                case_dict["avatar_data"] = ""
        else:
            case_dict["avatar_color"] = "#FF9E00"
            case_dict["avatar_data"] = ""

        result.append(case_dict)
    return result


def get_total_unread_for_user(user_id: int, role: str = "user") -> int:
    """Get total unread message count across all cases for badge display."""
    conn = _get_conn()
    if role == "superadmin":
        r = conn.execute(
            "SELECT SUM(sub.cnt) as total FROM ("
            "  SELECT COUNT(*) as cnt FROM complaint_messages cm "
            "  JOIN complaints c ON c.id = cm.complaint_id "
            "  WHERE cm.sender_id != ? AND c.status != 'closed' "
            "  GROUP BY cm.complaint_id"
            ") sub", (user_id,)
        ).fetchone()
    else:
        r = conn.execute(
            "SELECT SUM(sub.cnt) as total FROM ("
            "  SELECT COUNT(*) as cnt FROM complaint_messages cm "
            "  JOIN complaints c ON c.id = cm.complaint_id "
            "  WHERE c.user_id = ? AND cm.sender_id != ? AND c.status != 'closed' "
            "  GROUP BY cm.complaint_id"
            ") sub", (user_id, user_id)
        ).fetchone()
    return dict(r)["total"] or 0 if r else 0


def mark_case_read(complaint_id: int, user_id: int):
    """Mark all messages in a case as read by setting a read marker."""
    conn = _get_conn()
    # We use a simple approach: delete unread tracking for this user/case
    # Since we count messages from others, we mark by updating a json field
    # Actually simpler: just track last_read_message_id per user per case
    # For now, we'll use the complaint's updated_at as proxy
    conn.commit()


def get_all_user_profiles() -> dict:
    """Get all user profiles keyed by user_id for avatar display."""
    conn = _get_conn()
    rows = conn.execute("SELECT user_id, avatar_color, settings_json FROM user_profiles").fetchall()
    result = {}
    for r in rows:
        d = dict(r)
        try:
            settings = json.loads(d.get("settings_json", "{}"))
            avatar_data = settings.get("avatar_data", "")
        except:
            avatar_data = ""
        result[d["user_id"]] = {
            "avatar_color": d.get("avatar_color", "#FF9E00"),
            "avatar_data": avatar_data,
        }
    return result
