import hashlib
import hmac
import json
import sqlite3
import threading

from fastapi.testclient import TestClient

from dockship import db
from dockship.config import settings
from dockship.main import app


def test_malformed_signed_webhook_is_not_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "webhook.db"))
    db.init_db()
    body = json.dumps(["not", "a", "push", "object"]).encode()
    signature = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    client = TestClient(app)
    response = client.post(
        "/webhook/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "malformed-delivery",
        },
    )
    assert response.status_code == 400
    with db.connect() as conn:
        row = conn.execute(
            "SELECT id FROM deliveries WHERE id = ?",
            ("malformed-delivery",),
        ).fetchone()
    assert row is None


def test_duplicate_delivery_is_still_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "delivery.db"))
    db.init_db()
    assert db.record_delivery("same")
    assert not db.record_delivery("same")


def test_concurrent_app_registration_reserves_unique_ports(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "ports.db"))
    monkeypatch.setattr(settings, "port_min", 9100)
    monkeypatch.setattr(settings, "port_max", 9105)
    db.init_db()
    results = []
    errors = []

    def create(index):
        try:
            results.append(
                db.create_app(
                    f"app-{index}",
                    f"https://github.com/owner/app-{index}",
                    "main",
                    "/health",
                )
            )
        except (RuntimeError, sqlite3.Error) as exc:
            errors.append(exc)

    threads = [threading.Thread(target=create, args=(index,)) for index in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    port_pairs = {(row["blue_port"], row["green_port"]) for row in results}
    assert not errors
    assert len(results) == 3
    assert len(port_pairs) == 3


def test_pending_release_fields_migrate_and_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "pending.db"))
    db.init_db()
    db.create_app("hello", "https://github.com/owner/hello", "main", "/health")
    db.set_pending_release("hello", "blue", "a" * 40, "deployment-1")
    pending = db.list_pending_releases()
    assert len(pending) == 1
    assert pending[0]["pending_sha"] == "a" * 40
    db.clear_pending_release("hello")
    assert db.list_pending_releases() == []
