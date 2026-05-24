"""Unit tests for ``TodoService.bulk_action``.

Covers the main contract from the bulk-actions spec:
    - per-id outcomes (succeeded / no_change / not_found)
    - summary counts
    - id deduplication
    - validation errors for bad action / payload
    - spawn-once-per-series semantics on mark_done for recurring todos
    - atomic delete + remove from store
    - tag normalization (lowercased)
"""

from pathlib import Path

import pytest

from exceptions import ValidationError
from models import Recurrence, TodoCreate
from services.todo_service import TodoService
from store import JSONStore


@pytest.fixture
def svc(tmp_path: Path) -> TodoService:
    todos_file = tmp_path / "todos.json"
    todos_file.write_text("[]")
    return TodoService(JSONStore(str(todos_file)))


def test_bulk_mark_done_succeeds_and_dedupes_ids(svc):
    t1 = svc.create("u1", TodoCreate(title="A"))
    t2 = svc.create("u1", TodoCreate(title="B"))
    result = svc.bulk_action("u1", [t1.id, t2.id, t1.id], "mark_done", None)
    assert result["summary"]["total"] == 2
    assert result["summary"]["succeeded"] == 2
    assert result["outcomes"][t1.id]["status"] == "succeeded"
    assert result["outcomes"][t2.id]["status"] == "succeeded"


def test_bulk_returns_no_change_when_already_in_state(svc):
    t1 = svc.create("u1", TodoCreate(title="A", status="done"))
    result = svc.bulk_action("u1", [t1.id], "mark_done", None)
    assert result["outcomes"][t1.id]["status"] == "no_change"
    assert result["summary"]["no_change"] == 1
    assert result["summary"]["succeeded"] == 0


def test_bulk_not_found_for_unknown_or_other_users_id(svc):
    mine = svc.create("u1", TodoCreate(title="mine"))
    not_mine = svc.create("other", TodoCreate(title="not mine"))
    result = svc.bulk_action(
        "u1", [mine.id, not_mine.id, "missing-id"], "mark_done", None
    )
    assert result["outcomes"][mine.id]["status"] == "succeeded"
    assert result["outcomes"][not_mine.id]["status"] == "not_found"
    assert result["outcomes"]["missing-id"]["status"] == "not_found"
    assert result["summary"]["not_found"] == 2


def test_bulk_delete_removes_records(svc):
    t1 = svc.create("u1", TodoCreate(title="A"))
    t2 = svc.create("u1", TodoCreate(title="B"))
    result = svc.bulk_action("u1", [t1.id, t2.id], "delete", None)
    assert result["summary"]["succeeded"] == 2
    remaining = svc.list_todos(user_id="u1")
    assert remaining == []


def test_bulk_invalid_action_raises(svc):
    t1 = svc.create("u1", TodoCreate(title="A"))
    with pytest.raises(ValidationError):
        svc.bulk_action("u1", [t1.id], "explode", None)


def test_bulk_set_priority_validates_enum(svc):
    t1 = svc.create("u1", TodoCreate(title="A"))
    with pytest.raises(ValidationError):
        svc.bulk_action("u1", [t1.id], "set_priority", {"priority": "urgent"})


def test_bulk_add_tag_normalizes_lowercase(svc):
    t1 = svc.create("u1", TodoCreate(title="A"))
    svc.bulk_action("u1", [t1.id], "add_tag", {"tag": "  Work  "})
    refreshed = svc.get_by_id("u1", t1.id)
    assert "work" in refreshed.tags


def test_bulk_remove_tag_succeeds_and_no_change_when_absent(svc):
    t1 = svc.create("u1", TodoCreate(title="A", tags=["work"]))
    t2 = svc.create("u1", TodoCreate(title="B"))
    result = svc.bulk_action("u1", [t1.id, t2.id], "remove_tag", {"tag": "work"})
    assert result["outcomes"][t1.id]["status"] == "succeeded"
    assert result["outcomes"][t2.id]["status"] == "no_change"


def test_bulk_mark_done_recurring_spawns_once_per_series(svc):
    """If multiple occurrences of the same series get marked done in one call,
    only ONE next occurrence should be spawned (per series)."""
    t1 = svc.create(
        "u1",
        TodoCreate(
            title="Daily standup",
            due_date="2026-01-01",
            recurrence=Recurrence.DAILY,
        ),
    )
    # Manually create a sibling in the same series by emulating the next spawn
    # via a second mark_done call on t1 first, then bulk-completing both.
    svc.update("u1", t1.id, type(t1)(**{}).__class__.model_validate({"status": "done"}) if False else __import__("models").TodoUpdate(status="done"))
    todos = svc.list_todos(user_id="u1")
    pending = [t for t in todos if t.status.value != "done"]
    assert len(pending) == 1, "first done should have spawned one next occurrence"
    next_occ = pending[0]
    # Reset t1 to pending so we can mark both in the same bulk call
    svc.update("u1", t1.id, __import__("models").TodoUpdate(status="pending"))

    before_count = len(svc.list_todos(user_id="u1"))
    result = svc.bulk_action("u1", [t1.id, next_occ.id], "mark_done", None)
    after = svc.list_todos(user_id="u1")
    # Two completions in one bulk call → at most one additional occurrence
    # spawned (deduped by series_id).
    assert result["summary"]["succeeded"] == 2
    assert len(after) - before_count <= 1
