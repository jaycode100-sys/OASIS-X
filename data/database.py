import sqlite3, json, os, threading
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DB_DIR, "oasis.db")

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
    """)
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
