"""Pure functions for computing completion-streak statistics.

A *completion-day* is any UTC calendar date on which the user has at
least one todo whose ``status == "done"`` and whose ``updated_at``
parses to that date. We use ``updated_at`` as a completion proxy
matching the existing dashboard-stats pattern.

The functions here are deliberately pure so they are easy to test
without spinning up a JSONStore or FastAPI client.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Iterable


def _to_utc_date(raw: object) -> date | None:
    """Parse any ``datetime | str`` to a UTC date, or return None.

    Accepts ISO-8601 strings (with or without timezone) and ``datetime``
    objects. Naive datetimes are assumed to already be UTC.
    """
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
    elif isinstance(raw, str):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date()


def compute_streak(todos: Iterable[dict], now: datetime | None = None) -> dict:
    """Compute streak stats for a user's todos.

    Args:
        todos: An iterable of todo dicts (or model dumps). Only items
            with ``status == "done"`` count toward completion-days.
        now: The reference "current" timestamp. Defaults to ``datetime.now(UTC)``.
            Exposed for deterministic tests.

    Returns:
        ``{today_completed, week_completed, current_streak_days,
        longest_streak_days, last_completion_date}``.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    today: date = now.astimezone(timezone.utc).date()

    # Map each completion-day to a count, then derive the rest.
    by_day: dict[date, int] = {}
    for t in todos:
        if t.get("status") != "done":
            continue
        d = _to_utc_date(t.get("updated_at")) or _to_utc_date(t.get("created_at"))
        if d is None:
            continue
        by_day[d] = by_day.get(d, 0) + 1

    if not by_day:
        return {
            "today_completed": 0,
            "week_completed": 0,
            "current_streak_days": 0,
            "longest_streak_days": 0,
            "last_completion_date": None,
        }

    sorted_days = sorted(by_day.keys())

    # Longest streak: walk ascending, reset on gap > 1.
    longest = 1
    run = 1
    for prev, cur in zip(sorted_days, sorted_days[1:]):
        if (cur - prev).days == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1

    # Current streak: count back from today (or yesterday if today is empty).
    current = 0
    if today in by_day:
        anchor = today
    elif (today - timedelta(days=1)) in by_day:
        anchor = today - timedelta(days=1)
    else:
        anchor = None
    if anchor is not None:
        cursor = anchor
        while cursor in by_day:
            current += 1
            cursor -= timedelta(days=1)

    # Today / week counts.
    today_completed = by_day.get(today, 0)
    week_cutoff = today - timedelta(days=6)  # inclusive: today + 6 prior days
    week_completed = sum(
        count for d, count in by_day.items() if week_cutoff <= d <= today
    )

    return {
        "today_completed": today_completed,
        "week_completed": week_completed,
        "current_streak_days": current,
        "longest_streak_days": longest,
        "last_completion_date": sorted_days[-1].isoformat(),
    }
