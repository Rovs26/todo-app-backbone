"""Unit tests for the pure ``compute_streak`` function."""

from datetime import datetime, timezone

from services.streak_service import compute_streak


def _done_on(date_str: str) -> dict:
    return {"status": "done", "updated_at": f"{date_str}T12:00:00+00:00"}


def _pending_on(date_str: str) -> dict:
    return {"status": "pending", "updated_at": f"{date_str}T12:00:00+00:00"}


NOW = datetime(2026, 5, 25, 9, 0, tzinfo=timezone.utc)  # Mon 2026-05-25


def test_zero_todos_returns_zeros():
    result = compute_streak([], now=NOW)
    assert result == {
        "today_completed": 0,
        "week_completed": 0,
        "current_streak_days": 0,
        "longest_streak_days": 0,
        "last_completion_date": None,
    }


def test_only_pending_todos_dont_count():
    result = compute_streak([_pending_on("2026-05-25")], now=NOW)
    assert result["today_completed"] == 0
    assert result["current_streak_days"] == 0


def test_one_done_today():
    result = compute_streak([_done_on("2026-05-25")], now=NOW)
    assert result["today_completed"] == 1
    assert result["week_completed"] == 1
    assert result["current_streak_days"] == 1
    assert result["longest_streak_days"] == 1
    assert result["last_completion_date"] == "2026-05-25"


def test_consecutive_run_includes_today():
    todos = [_done_on(d) for d in ("2026-05-23", "2026-05-24", "2026-05-25")]
    result = compute_streak(todos, now=NOW)
    assert result["current_streak_days"] == 3
    assert result["longest_streak_days"] == 3


def test_today_empty_but_yesterday_filled_returns_run_ending_yesterday():
    todos = [_done_on(d) for d in ("2026-05-23", "2026-05-24")]
    result = compute_streak(todos, now=NOW)
    assert result["today_completed"] == 0
    assert result["current_streak_days"] == 2  # anchored to yesterday


def test_broken_streak_resets():
    # Last done was 3 days ago — neither today nor yesterday → 0
    result = compute_streak([_done_on("2026-05-22")], now=NOW)
    assert result["current_streak_days"] == 0
    assert result["longest_streak_days"] == 1


def test_longest_streak_finds_max_across_history():
    todos = [
        _done_on("2026-05-01"),
        _done_on("2026-05-02"),
        _done_on("2026-05-03"),
        _done_on("2026-05-04"),  # 4-day run
        _done_on("2026-05-10"),
        _done_on("2026-05-11"),  # 2-day run
    ]
    result = compute_streak(todos, now=NOW)
    assert result["longest_streak_days"] == 4
    assert result["current_streak_days"] == 0  # nothing within today/yesterday


def test_cross_month_boundary_run():
    # Apr 29, 30, May 1 — three consecutive days across month boundary.
    todos = [_done_on(d) for d in ("2026-04-29", "2026-04-30", "2026-05-01")]
    result = compute_streak(todos, now=NOW)
    assert result["longest_streak_days"] == 3


def test_week_completed_window_is_last_7_days_inclusive():
    # 7 days inclusive of today = 2026-05-19 .. 2026-05-25
    todos = [
        _done_on("2026-05-18"),  # outside window
        _done_on("2026-05-19"),  # inside (boundary)
        _done_on("2026-05-25"),  # inside
    ]
    result = compute_streak(todos, now=NOW)
    assert result["week_completed"] == 2


def test_multiple_done_same_day_count_separately_in_today_completed():
    todos = [_done_on("2026-05-25"), _done_on("2026-05-25")]
    result = compute_streak(todos, now=NOW)
    assert result["today_completed"] == 2
    assert result["current_streak_days"] == 1  # still one day
