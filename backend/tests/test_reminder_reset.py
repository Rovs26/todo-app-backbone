"""Tests for Property 4 — reminder_at change resets sent state."""

from pathlib import Path

import pytest

from models import TodoCreate, TodoUpdate
from services.todo_service import TodoService
from store import JSONStore


@pytest.fixture
def svc(tmp_path: Path) -> TodoService:
    f = tmp_path / "todos.json"
    f.write_text("[]")
    return TodoService(JSONStore(str(f)))


def test_changing_reminder_at_resets_sent_state(svc):
    t = svc.create("u1", TodoCreate(title="A", reminder_at="2026-12-01T09:00:00+00:00"))
    # Simulate the scheduler marking it sent
    records = svc.todo_store.read_all()
    records[0]["reminder_sent"] = True
    records[0]["reminder_sent_at"] = "2026-12-01T09:00:30+00:00"
    svc.todo_store.write_all(records)

    updated = svc.update("u1", t.id, TodoUpdate(reminder_at="2026-12-05T09:00:00+00:00"))
    assert updated.reminder_sent is False
    assert updated.reminder_sent_at is None


def test_clearing_reminder_at_resets_sent_state(svc):
    t = svc.create("u1", TodoCreate(title="A", reminder_at="2026-12-01T09:00:00+00:00"))
    records = svc.todo_store.read_all()
    records[0]["reminder_sent"] = True
    records[0]["reminder_sent_at"] = "2026-12-01T09:00:30+00:00"
    svc.todo_store.write_all(records)

    updated = svc.update("u1", t.id, TodoUpdate(reminder_at=""))
    assert updated.reminder_at is None
    assert updated.reminder_sent is False
    assert updated.reminder_sent_at is None


def test_update_without_reminder_at_preserves_sent_state(svc):
    t = svc.create("u1", TodoCreate(title="A", reminder_at="2026-12-01T09:00:00+00:00"))
    records = svc.todo_store.read_all()
    records[0]["reminder_sent"] = True
    records[0]["reminder_sent_at"] = "2026-12-01T09:00:30+00:00"
    svc.todo_store.write_all(records)

    updated = svc.update("u1", t.id, TodoUpdate(title="A renamed"))
    assert updated.reminder_sent is True
    assert updated.reminder_sent_at is not None
