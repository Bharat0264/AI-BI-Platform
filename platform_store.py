"""Small persistent workspace store for the local BI platform."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "platform.db"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_store():
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS records (
          id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
          name TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
          key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        """)
        defaults = {
            "current_user": {"name": "Bharath", "role": "Admin", "workspace": "Executive Workspace"},
            "semantic_metrics": [
                {"name": "Net Revenue", "column": "Sales", "aggregation": "sum", "format": "currency"},
                {"name": "Gross Profit", "column": "Profit", "aggregation": "sum", "format": "currency"},
                {"name": "Profit Margin", "formula": "Profit / Sales", "format": "percent"},
            ],
        }
        for key, value in defaults.items():
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)", (key, json.dumps(value)))


def list_records(kind):
    with connection() as db:
        rows = db.execute("SELECT * FROM records WHERE kind=? ORDER BY id DESC", (kind,)).fetchall()
    return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]


def add_record(kind, name, payload):
    with connection() as db:
        cursor = db.execute(
            "INSERT INTO records(kind,name,payload,created_at) VALUES (?,?,?,?)",
            (kind, name, json.dumps(payload), now()),
        )
        record_id = cursor.lastrowid
    return get_record(record_id)


def get_record(record_id):
    with connection() as db:
        row = db.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
    return {**dict(row), "payload": json.loads(row["payload"])} if row else None


def update_record(record_id, payload):
    existing = get_record(record_id)
    if not existing:
        return None
    merged = {**existing["payload"], **payload}
    name = str(payload.get("name", existing["name"]))
    with connection() as db:
        db.execute("UPDATE records SET name=?,payload=? WHERE id=?", (name, json.dumps(merged), record_id))
    return get_record(record_id)


def delete_record(record_id):
    with connection() as db:
        return db.execute("DELETE FROM records WHERE id=?", (record_id,)).rowcount > 0


def get_setting(key, default=None):
    with connection() as db:
        row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def set_setting(key, value):
    with connection() as db:
        db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)", (key, json.dumps(value)))
    return value
