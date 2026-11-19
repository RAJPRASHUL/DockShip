import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
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


def get_app(name: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM apps WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None


def create_app(name: str, repo_url: str, branch: str, health_path: str) -> dict:
    from dockship.ports import allocate_ports

    blue_port, green_port = allocate_ports()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO apps (name, repo_url, branch, health_path, blue_port, green_port)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, repo_url, branch, health_path, blue_port, green_port),
        )
        conn.commit()
    return get_app(name)  # type: ignore[return-value]


def new_deployment(app_name: str, trigger: str) -> str:
    deployment_id = str(uuid.uuid4())
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO deployments (id, app_name, trigger, status, started_at)
            VALUES (?, ?, ?, 'queued', ?)
            """,
            (deployment_id, app_name, trigger, datetime.now(UTC).isoformat()),
        )
        conn.commit()
    return deployment_id


def update_deployment(deployment_id: str, **fields) -> None:
    allowed = {"sha", "status", "error", "duration_s"}
    values = {key: value for key, value in fields.items() if key in allowed}
    if not values:
        return
    assignments = ", ".join(f"{key} = ?" for key in values)
    with connect() as conn:
        conn.execute(
            f"UPDATE deployments SET {assignments} WHERE id = ?",
            (*values.values(), deployment_id),
        )
        conn.commit()


def get_deployment(deployment_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM deployments WHERE id = ?", (deployment_id,)
        ).fetchone()
        return dict(row) if row else None


def set_release(app_name: str, color: str, sha: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE apps
            SET previous_sha = current_sha, current_sha = ?, active_color = ?
            WHERE name = ?
            """,
            (sha, color, app_name),
        )
        conn.commit()
