"""Tests for SQLStore (parity with JSONStore) + the migration script."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from db import init_db, make_engine, make_session_factory
from store import SQLStore


# --- Fixtures ---------------------------------------------------------------


@pytest.fixture
def session_factory(tmp_path: Path):
    """Per-test on-disk SQLite (file-based, not :memory:, so multiple
    SQLStore instances bound to the same factory all see each other)."""
    db_path = tmp_path / "test.db"
    engine = make_engine(f"sqlite:///{db_path}")
    init_db(engine)
    return make_session_factory(engine)


# --- SQLStore CRUD parity ---------------------------------------------------


def test_folder_round_trip_through_sqlstore(session_factory):
    store = SQLStore(session_factory, "data/folders.json")
    assert store.read_all() == []

    record = {
        "id": "f1",
        "user_id": "u1",
        "name": "Inbox",
        "color": "#abc",
        "icon": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": None,
    }
    store.add(record)

    assert store.find_by_id("f1") == record
    assert store.find_by_field("name", "Inbox")["id"] == "f1"
    assert store.find_by_field("name", "Nope") is None

    updated = store.update("f1", {"name": "Renamed"})
    assert updated["name"] == "Renamed"
    assert store.find_by_id("f1")["name"] == "Renamed"

    assert store.delete("f1") is True
    assert store.delete("f1") is False
    assert store.read_all() == []


def test_update_unknown_id_returns_none(session_factory):
    store = SQLStore(session_factory, "data/folders.json")
    assert store.update("missing", {"name": "X"}) is None


def test_todo_nested_fields_round_trip(session_factory):
    store = SQLStore(session_factory, "data/todos.json")
    record = {
        "id": "t1",
        "user_id": "u1",
        "title": "Pay bills",
        "priority": "high",
        "status": "pending",
        "tags": ["finance", "urgent"],
        "subtasks": [{"id": "s1", "title": "rent", "done": False}],
        "comments": [],
        "created_at": "2026-01-01T00:00:00Z",
        "position": 3,
        "reminder_sent": False,
        "time_spent_seconds": 0,
        "recurrence": "monthly",
        "recurrence_index": 0,
    }
    store.add(record)
    loaded = store.find_by_id("t1")
    assert loaded["tags"] == ["finance", "urgent"]
    assert loaded["subtasks"] == [{"id": "s1", "title": "rent", "done": False}]
    assert loaded["priority"] == "high"
    assert loaded["recurrence"] == "monthly"


def test_write_all_replaces_collection_atomically(session_factory):
    store = SQLStore(session_factory, "data/folders.json")
    base = {
        "user_id": "u1",
        "name": "n",
        "color": None,
        "icon": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": None,
    }
    store.add({**base, "id": "f1"})
    store.add({**base, "id": "f2"})
    assert {r["id"] for r in store.read_all()} == {"f1", "f2"}

    store.write_all([{**base, "id": "f3", "name": "Only"}])
    rows = store.read_all()
    assert len(rows) == 1
    assert rows[0]["id"] == "f3" and rows[0]["name"] == "Only"


def test_add_without_id_raises(session_factory):
    store = SQLStore(session_factory, "data/folders.json")
    with pytest.raises(ValueError):
        store.add({"name": "no-id"})


def test_unknown_collection_raises(session_factory):
    with pytest.raises(ValueError):
        SQLStore(session_factory, "data/unknown.json")


def test_two_stores_same_table_share_state(session_factory):
    a = SQLStore(session_factory, "data/folders.json")
    b = SQLStore(session_factory, "data/folders.json")
    a.add({
        "id": "f1", "user_id": "u1", "name": "X", "color": None, "icon": None,
        "created_at": "2026-01-01T00:00:00Z", "updated_at": None,
    })
    assert b.find_by_id("f1") is not None


# --- Migration script -------------------------------------------------------


def _write_json(path: Path, records: list[dict]) -> None:
    path.write_text(json.dumps(records), encoding="utf-8")


def test_migration_inserts_rows_and_is_idempotent(tmp_path: Path):
    from scripts.migrate_json_to_sqlite import migrate

    _write_json(tmp_path / "users.json", [{
        "id": "u1", "email": "a@b.com", "username": "a",
        "password_hash": "h", "created_at": "2026-01-01T00:00:00Z",
        "email_reminders_enabled": True,
    }])
    _write_json(tmp_path / "folders.json", [{
        "id": "f1", "user_id": "u1", "name": "Inbox",
        "color": None, "icon": None,
        "created_at": "2026-01-01T00:00:00Z", "updated_at": None,
    }])
    _write_json(tmp_path / "todos.json", [{
        "id": "t1", "user_id": "u1", "title": "Pay bills",
        "priority": "high", "status": "pending",
        "tags": ["x"], "subtasks": [], "comments": [],
        "created_at": "2026-01-01T00:00:00Z",
    }])

    inserted_first = migrate(tmp_path)
    assert inserted_first == 3

    # Backup files created.
    assert (tmp_path / "users.json.bak").exists()
    assert (tmp_path / "folders.json.bak").exists()
    assert (tmp_path / "todos.json.bak").exists()

    # Idempotent: a second run inserts nothing.
    inserted_second = migrate(tmp_path)
    assert inserted_second == 0


def test_migration_skips_rows_without_id(tmp_path: Path):
    from scripts.migrate_json_to_sqlite import migrate

    _write_json(tmp_path / "folders.json", [
        {"name": "no-id"},
        {"id": "f1", "user_id": "u1", "name": "ok",
         "color": None, "icon": None,
         "created_at": "2026-01-01T00:00:00Z", "updated_at": None},
    ])
    inserted = migrate(tmp_path)
    assert inserted == 1


def test_rollback_round_trip(tmp_path: Path):
    from scripts.migrate_json_to_sqlite import migrate
    from scripts.rollback_sqlite_to_json import rollback

    _write_json(tmp_path / "folders.json", [{
        "id": "f1", "user_id": "u1", "name": "Inbox",
        "color": "#abc", "icon": None,
        "created_at": "2026-01-01T00:00:00Z", "updated_at": None,
    }])
    migrate(tmp_path)

    # Delete the original to force rollback to recreate it.
    (tmp_path / "folders.json").unlink()
    exported = rollback(tmp_path)
    # 1 folder + every other empty table contributes 0 rows.
    assert exported == 1

    restored = json.loads((tmp_path / "folders.json").read_text())
    assert restored[0]["id"] == "f1"
    assert restored[0]["color"] == "#abc"
