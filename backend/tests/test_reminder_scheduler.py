"""Unit tests for the ReminderScheduler dispatch logic.

We exercise ``_dispatch`` and ``_select_due`` directly with an in-memory
email backend; the polling loop itself isn't exercised (no need to spin
up asyncio sleep).
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services.email_service import EmailService, InMemoryBackend
from services.reminder_scheduler import ReminderScheduler
from store import JSONStore


# --- fixtures ----------------------------------------------------------------


@pytest.fixture
def stores(tmp_path: Path):
    todo_store = JSONStore(str(tmp_path / "todos.json"))
    user_store = JSONStore(str(tmp_path / "users.json"))
    log_store = JSONStore(str(tmp_path / "log.json"))
    return todo_store, user_store, log_store


def _make_scheduler(stores, *, backend=None, rate=100):
    todo_store, user_store, log_store = stores
    backend = backend or InMemoryBackend()
    svc = EmailService(backend=backend, frontend_url="http://app")
    sched = ReminderScheduler(
        todo_store=todo_store,
        user_store=user_store,
        email_service=svc,
        log_store=log_store,
        rate_limit_per_minute=rate,
    )
    return sched, backend


def _now():
    return datetime.now(timezone.utc)


def _make_user(user_store, *, opted_out=False):
    uid = str(uuid.uuid4())
    user_store.add(
        {
            "id": uid,
            "email": f"{uid}@example.com",
            "username": "alice",
            "password_hash": "hash",
            "created_at": _now().isoformat(),
            "email_reminders_enabled": not opted_out,
        }
    )
    return uid


def _make_todo(todo_store, user_id, *, reminder_at, sent=False):
    tid = str(uuid.uuid4())
    todo_store.add(
        {
            "id": tid,
            "user_id": user_id,
            "title": "Pay rent",
            "due_date": "2026-12-01",
            "priority": "medium",
            "status": "pending",
            "reminder_at": reminder_at.isoformat() if reminder_at else None,
            "reminder_sent": sent,
            "reminder_sent_at": None,
            "created_at": _now().isoformat(),
        }
    )
    return tid


# --- _select_due -------------------------------------------------------------


def test_select_due_picks_only_past_and_unsent(stores):
    todo_store, user_store, log_store = stores
    uid = _make_user(user_store)
    now = _now()
    past_unsent = _make_todo(todo_store, uid, reminder_at=now - timedelta(minutes=1))
    _make_todo(todo_store, uid, reminder_at=now - timedelta(minutes=1), sent=True)
    _make_todo(todo_store, uid, reminder_at=now + timedelta(hours=1))
    _make_todo(todo_store, uid, reminder_at=None)
    sched, _ = _make_scheduler(stores)

    due = sched._select_due(now)
    assert [d["id"] for d in due] == [past_unsent]


# --- _dispatch: success path -------------------------------------------------


def test_dispatch_success_marks_sent_and_logs_property_2_property_13(stores):
    todo_store, user_store, log_store = stores
    uid = _make_user(user_store)
    now = _now()
    tid = _make_todo(todo_store, uid, reminder_at=now - timedelta(minutes=1))
    sched, backend = _make_scheduler(stores)

    todo_row = next(r for r in todo_store.read_all() if r["id"] == tid)
    asyncio.run(sched._dispatch(todo_row, now))

    refreshed = next(r for r in todo_store.read_all() if r["id"] == tid)
    assert refreshed["reminder_sent"] is True
    assert refreshed["reminder_sent_at"] is not None
    assert len(backend.sent) == 1

    log_entries = log_store.read_all()
    assert len(log_entries) == 1
    assert log_entries[0]["status"] == "sent"
    assert log_entries[0]["attempt_count"] == 1
    assert log_entries[0]["todo_id"] == tid


# --- _dispatch: opt-out ------------------------------------------------------


def test_dispatch_opted_out_short_circuits_property_5(stores):
    todo_store, user_store, log_store = stores
    uid = _make_user(user_store, opted_out=True)
    now = _now()
    tid = _make_todo(todo_store, uid, reminder_at=now - timedelta(minutes=1))
    sched, backend = _make_scheduler(stores)

    todo_row = next(r for r in todo_store.read_all() if r["id"] == tid)
    asyncio.run(sched._dispatch(todo_row, now))

    assert backend.sent == []
    refreshed = next(r for r in todo_store.read_all() if r["id"] == tid)
    assert refreshed["reminder_sent"] is True
    assert log_store.read_all()[0]["status"] == "skipped_optout"


# --- _dispatch: missing user -------------------------------------------------


def test_dispatch_missing_user_short_circuits_property_6(stores):
    todo_store, user_store, log_store = stores
    now = _now()
    tid = _make_todo(
        todo_store, "ghost-user", reminder_at=now - timedelta(minutes=1)
    )
    sched, backend = _make_scheduler(stores)

    todo_row = next(r for r in todo_store.read_all() if r["id"] == tid)
    asyncio.run(sched._dispatch(todo_row, now))

    assert backend.sent == []
    refreshed = next(r for r in todo_store.read_all() if r["id"] == tid)
    assert refreshed["reminder_sent"] is True
    assert log_store.read_all()[0]["status"] == "skipped_user_missing"


# --- _dispatch: retry succeeds on attempt 3 ----------------------------------


def test_dispatch_retries_and_succeeds_property_3(stores, monkeypatch):
    # Patch asyncio.wait_for to short-circuit the backoff sleeps so the
    # test runs in milliseconds instead of 30 s.
    async def _instant(awaitable, timeout):  # noqa: ARG001
        raise asyncio.TimeoutError

    monkeypatch.setattr(
        "services.reminder_scheduler.asyncio.wait_for", _instant
    )

    todo_store, user_store, log_store = stores
    uid = _make_user(user_store)
    now = _now()
    tid = _make_todo(todo_store, uid, reminder_at=now - timedelta(minutes=1))
    backend = InMemoryBackend(fail_first=2)  # attempts 1+2 fail, attempt 3 succeeds
    sched, _ = _make_scheduler(stores, backend=backend)

    todo_row = next(r for r in todo_store.read_all() if r["id"] == tid)
    asyncio.run(sched._dispatch(todo_row, now))

    assert len(backend.sent) == 1
    log_entries = log_store.read_all()
    assert log_entries[0]["status"] == "sent"
    assert log_entries[0]["attempt_count"] == 3


# --- _dispatch: total failure logs failed with attempt_count=3 ---------------


def test_dispatch_all_attempts_fail_logs_failed_property_3(stores, monkeypatch):
    async def _instant(awaitable, timeout):  # noqa: ARG001
        raise asyncio.TimeoutError

    monkeypatch.setattr(
        "services.reminder_scheduler.asyncio.wait_for", _instant
    )

    todo_store, user_store, log_store = stores
    uid = _make_user(user_store)
    now = _now()
    tid = _make_todo(todo_store, uid, reminder_at=now - timedelta(minutes=1))
    backend = InMemoryBackend(fail_first=10)  # always fails
    sched, _ = _make_scheduler(stores, backend=backend)

    todo_row = next(r for r in todo_store.read_all() if r["id"] == tid)
    asyncio.run(sched._dispatch(todo_row, now))

    refreshed = next(r for r in todo_store.read_all() if r["id"] == tid)
    assert refreshed["reminder_sent"] is True
    entry = log_store.read_all()[0]
    assert entry["status"] == "failed"
    assert entry["attempt_count"] == 3
    assert entry["error_class"] == "RuntimeError"


# --- _apply_rate_cap ---------------------------------------------------------


def test_apply_rate_cap_defers_overflow_property_7(stores):
    todo_store, user_store, log_store = stores
    uid = _make_user(user_store)
    now = _now()
    due = [
        {"id": _make_todo(todo_store, uid, reminder_at=now - timedelta(minutes=1))}
        for _ in range(5)
    ]
    sched, _ = _make_scheduler(stores, rate=3)
    # Seed three recent "sent" log entries so headroom == 0
    log_store.write_all(
        [
            {
                "id": "x",
                "todo_id": "t",
                "user_id": uid,
                "email": "",
                "attempted_at": (now - timedelta(seconds=10)).isoformat(),
                "status": "sent",
                "attempt_count": 1,
            }
            for _ in range(3)
        ]
    )
    capped = sched._apply_rate_cap(due, now)
    assert capped == []  # cap reached
