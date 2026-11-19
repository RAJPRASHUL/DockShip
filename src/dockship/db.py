import sqlite3
from contextlib import contextmanager
from pathlib import Path

from dockship.config import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS apps (
    name TEXT PRIMARY KEY,
    repo_url TEXT NOT NULL,
    branch TEXT NOT NULL,
    health_path TEXT NOT NULL DEFAULT '/health',
    blue_port INTEGER,
    green_port INTEGER,
    active_color TEXT,
    current_sha TEXT,
    previous_sha TEXT
);

CREATE TABLE IF NOT EXISTS deployments (
    id TEXT PRIMARY KEY,
    app_name TEXT NOT NULL,
    trigger TEXT NOT NULL,
    sha TEXT,
    status TEXT NOT NULL,
    error TEXT,
    duration_s REAL,
    started_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deliveries (
    id TEXT PRIMARY KEY,
    received_at TEXT NOT NULL
);
"""


@contextmanager
def connect():
    path = Path(settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def list_apps() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM apps ORDER BY name").fetchall()
        return [dict(row) for row in rows]
