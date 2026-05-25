"""Asyncio polling scheduler that dispatches email reminders.

Runs in-process. Every ``POLL_INTERVAL_SECONDS`` seconds it scans
``todos.json`` for todos whose ``reminder_at`` has passed but whose
``reminder_sent`` flag is still ``False``. For each one it looks up the
owning user, branches into opt-out / missing-user / send paths, persists
the outcome to ``todos.json``, and appends a structured entry to
``data/reminder_send_log.json``.

Retry policy: 3 attempts total with 5s and 25s backoff. Each dispatch
runs as its own asyncio task so a slow SMTP server cannot delay other
reminders.

Rate limit: at most ``rate_limit_per_minute`` dispatches per rolling 60s
window. The window is measured from the send-log's ``attempted_at``
timestamps to survive restarts.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from services.email_service import EmailService
from store import JSONStore

log = logging.getLogger(__name__)

_LOG_CAP = 10_000
_LOG_TRIM = 1_000


class ReminderScheduler:
    POLL_INTERVAL_SECONDS = 60
    BACKOFFS = (5, 25)  # delay before attempt 2 and 3
    MAX_ATTEMPTS = 3

    def __init__(
        self,
        *,
        todo_store: JSONStore,
        user_store: JSONStore,
        email_service: EmailService,
        log_store: JSONStore,
        rate_limit_per_minute: int = 100,
    ):
        self.todo_store = todo_store
        self.user_store = user_store
        self.email_service = email_service
        self.log_store = log_store
        self.rate_limit_per_minute = rate_limit_per_minute
        self._stop = asyncio.Event()
        self._in_flight: set[asyncio.Task] = set()

    async def run(self) -> None:
        """Main polling loop. Exits when ``stop()`` is called."""
        while not self._stop.is_set():
            try:
                await self._tick()
            except Exception:  # pragma: no cover - defensive
                log.exception("ReminderScheduler tick failed; resuming next cycle")
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=self.POLL_INTERVAL_SECONDS
                )
            except asyncio.TimeoutError:
                pass

    async def stop(self) -> None:
        """Signal the loop to exit; wait briefly for in-flight dispatches."""
        self._stop.set()
        if self._in_flight:
            await asyncio.wait(self._in_flight, timeout=5.0)

    async def _tick(self) -> None:
        now = datetime.now(timezone.utc)
        due = self._select_due(now)
        if not due:
            return
        capped = self._apply_rate_cap(due, now)
        deferred = len(due) - len(capped)
        if deferred > 0:
            log.warning(
                "ReminderScheduler deferred %d reminder(s) due to rate cap", deferred
            )
        for todo in capped:
            task = asyncio.create_task(self._dispatch(todo, now))
            self._in_flight.add(task)
            task.add_done_callback(self._in_flight.discard)

    def _select_due(self, now: datetime) -> list[dict]:
        records = self.todo_store.read_all()
        due: list[dict] = []
        for r in records:
            if r.get("reminder_sent"):
                continue
            raw = r.get("reminder_at")
            if not raw:
                continue
            dt = _parse_dt(raw)
            if dt is None or dt > now:
                continue
            due.append(r)
        return due

    def _apply_rate_cap(self, due: list[dict], now: datetime) -> list[dict]:
        if self.rate_limit_per_minute <= 0:
            return []
        window_start = now - timedelta(seconds=60)
        recent = 0
        for entry in self.log_store.read_all():
            ts = _parse_dt(entry.get("attempted_at"))
            if ts and ts >= window_start and entry.get("status") in {"sent", "failed"}:
                recent += 1
        headroom = max(0, self.rate_limit_per_minute - recent)
        return due[:headroom]

    async def _dispatch(self, todo: dict, started_at: datetime) -> None:
        todo_id = todo.get("id")
        user_id = todo.get("user_id")
        user_data = self.user_store.find_by_id(user_id) if user_id else None

        if not user_data:
            self._mark_sent(todo_id, started_at)
            self._append_log(
                todo_id=todo_id,
                user_id=user_id or "",
                email="",
                started_at=started_at,
                status="skipped_user_missing",
                attempt_count=1,
            )
            return

        email = user_data.get("email", "")
        if user_data.get("email_reminders_enabled", True) is False:
            self._mark_sent(todo_id, started_at)
            self._append_log(
                todo_id=todo_id,
                user_id=user_id,
                email=email,
                started_at=started_at,
                status="skipped_optout",
                attempt_count=1,
            )
            return

        last_error: Exception | None = None
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                await self.email_service.send_reminder(user_email=email, todo=todo)
                self._mark_sent(todo_id, datetime.now(timezone.utc))
                self._append_log(
                    todo_id=todo_id,
                    user_id=user_id,
                    email=email,
                    started_at=started_at,
                    status="sent",
                    attempt_count=attempt,
                )
                return
            except Exception as exc:
                last_error = exc
                if attempt < self.MAX_ATTEMPTS:
                    backoff = self.BACKOFFS[attempt - 1]
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                        return  # stop signaled mid-retry; let next process retry
                    except asyncio.TimeoutError:
                        continue

        # All attempts exhausted
        self._mark_sent(todo_id, datetime.now(timezone.utc))
        err_cls = type(last_error).__name__ if last_error else ""
        err_msg = (str(last_error) if last_error else "")[:500]
        self._append_log(
            todo_id=todo_id,
            user_id=user_id,
            email=email,
            started_at=started_at,
            status="failed",
            attempt_count=self.MAX_ATTEMPTS,
            error_class=err_cls,
            error_message=err_msg,
        )

    # --- Persistence helpers -------------------------------------------------

    def _mark_sent(self, todo_id: str | None, when: datetime) -> None:
        if not todo_id:
            return
        records = self.todo_store.read_all()
        for r in records:
            if r.get("id") == todo_id:
                r["reminder_sent"] = True
                r["reminder_sent_at"] = when.isoformat()
                break
        self.todo_store.write_all(records)

    def _append_log(
        self,
        *,
        todo_id: str | None,
        user_id: str,
        email: str,
        started_at: datetime,
        status: str,
        attempt_count: int,
        error_class: str = "",
        error_message: str = "",
    ) -> None:
        entries = self.log_store.read_all()
        if len(entries) > _LOG_CAP:
            entries = entries[_LOG_TRIM:]
        entry: dict = {
            "id": str(uuid.uuid4()),
            "todo_id": todo_id or "",
            "user_id": user_id,
            "email": email,
            "attempted_at": started_at.isoformat(),
            "status": status,
            "attempt_count": attempt_count,
        }
        if error_class:
            entry["error_class"] = error_class
        if error_message:
            entry["error_message"] = error_message
        entries.append(entry)
        self.log_store.write_all(entries)


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
