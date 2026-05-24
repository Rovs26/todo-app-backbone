"""DST-safe calendar arithmetic for recurring todos.

`next_occurrence_date(due_date, recurrence)` returns the next ISO date
string after applying one recurrence interval. Month/year shifts clamp to
the last day of the target month when the source day doesn't exist (e.g.
Jan 31 + 1 month = Feb 28).
"""

from calendar import monthrange
from datetime import date, datetime, timedelta

from models import Recurrence


def _clamp_day(year: int, month: int, day: int) -> date:
    last = monthrange(year, month)[1]
    return date(year, month, min(day, last))


def next_occurrence_date(due_date_str: str, recurrence: str) -> str:
    """Return the next ISO date string after one recurrence interval."""
    base = date.fromisoformat(due_date_str)
    if recurrence == Recurrence.DAILY.value:
        nxt = base + timedelta(days=1)
    elif recurrence == Recurrence.WEEKLY.value:
        nxt = base + timedelta(days=7)
    elif recurrence == Recurrence.MONTHLY.value:
        y, m = base.year, base.month + 1
        if m > 12:
            y += 1
            m = 1
        nxt = _clamp_day(y, m, base.day)
    elif recurrence == Recurrence.YEARLY.value:
        nxt = _clamp_day(base.year + 1, base.month, base.day)
    else:
        raise ValueError(f"unsupported recurrence: {recurrence}")
    return nxt.isoformat()


def shift_reminder(reminder_at_iso: str, old_due: str, new_due: str) -> str:
    """Shift a reminder by the same delta applied to the due date."""
    old = date.fromisoformat(old_due)
    new = date.fromisoformat(new_due)
    delta = new - old
    parsed = datetime.fromisoformat(reminder_at_iso)
    return (parsed + delta).isoformat()
