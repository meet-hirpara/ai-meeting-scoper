import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "projects.db"

JSON_FIELDS = {
    "stage1_data", "stage2_data", "stage2_user_qa",
    "stage3_changelog", "stage4_data", "stage5_jira_config", "stage5_results",
}
LIST_FIELDS = {"stage2_data", "stage2_user_qa", "stage3_changelog"}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id                    TEXT PRIMARY KEY,
            name                  TEXT NOT NULL,
            created_at            TEXT NOT NULL,
            current_stage         INTEGER DEFAULT 1,
            transcript            TEXT DEFAULT '',
            stage1_data           TEXT DEFAULT '{}',
            stage1_approved       INTEGER DEFAULT 0,
            stage2_data           TEXT DEFAULT '[]',
            stage2_user_qa        TEXT DEFAULT '[]',
            stage2_approved       INTEGER DEFAULT 0,
            stage3_sow            TEXT DEFAULT '',
            stage3_changelog      TEXT DEFAULT '[]',
            stage3_feedback_count INTEGER DEFAULT 0,
            stage3_approved       INTEGER DEFAULT 0,
            stage4_data           TEXT DEFAULT '{}',
            stage4_approved       INTEGER DEFAULT 0,
            stage5_jira_config    TEXT DEFAULT '{}',
            stage5_results        TEXT DEFAULT '{}',
            stage5_approved       INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def _load_row(row):
    p = dict(row)
    for field in JSON_FIELDS:
        raw = p.get(field, "")
        try:
            p[field] = json.loads(raw) if raw else ([] if field in LIST_FIELDS else {})
        except Exception:
            p[field] = [] if field in LIST_FIELDS else {}
    return p


def create_project(name):
    pid = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO projects (id, name, created_at) VALUES (?, ?, ?)",
        (pid, name, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return get_project(pid)


def get_project(pid):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
    conn.close()
    return _load_row(row) if row else None


def list_projects():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, name, created_at, current_stage FROM projects ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_project(pid, **kwargs):
    if not kwargs:
        return
    cols = ", ".join(f"{k} = ?" for k in kwargs)
    vals = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in kwargs.values()]
    vals.append(pid)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(f"UPDATE projects SET {cols} WHERE id = ?", vals)
    conn.commit()
    conn.close()


def delete_project(pid):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM projects WHERE id = ?", (pid,))
    conn.commit()
    conn.close()
