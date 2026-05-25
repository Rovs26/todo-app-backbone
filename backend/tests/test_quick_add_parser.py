"""Tests for the deterministic local quick-add parser."""

from services.quick_add_parser import parse_local


def test_title_only():
    out = parse_local("buy bread")
    assert out == {"title": "buy bread"}


def test_priority_high():
    out = parse_local("ship release !high")
    assert out["title"] == "ship release"
    assert out["priority"] == "high"


def test_priority_med_alias():
    out = parse_local("review PR !med")
    assert out["priority"] == "medium"


def test_priority_low():
    out = parse_local("!low water plants")
    assert out["priority"] == "low"
    assert out["title"] == "water plants"


def test_tags_extracted_and_lowercased():
    out = parse_local("groceries #Shopping #Home")
    assert out["title"] == "groceries"
    assert out["tags"] == ["shopping", "home"]


def test_duplicate_tags_deduped():
    out = parse_local("a #x b #x c")
    assert out["tags"] == ["x"]
    assert out["title"] == "a b c"


def test_due_date_token():
    out = parse_local("pay rent @2026-12-01")
    assert out["due_date"] == "2026-12-01"
    assert out["title"] == "pay rent"


def test_recurrence_daily():
    out = parse_local("stretch every day")
    assert out["recurrence"] == "daily"
    assert out["title"] == "stretch"


def test_recurrence_monthly_with_priority_and_tag():
    out = parse_local("pay rent every month !high #bills")
    assert out == {
        "title": "pay rent",
        "priority": "high",
        "recurrence": "monthly",
        "tags": ["bills"],
    }


def test_tag_with_hash_only_is_ignored():
    # Bare '#' (no word) is not a tag; left as part of title
    out = parse_local("look at # tag")
    assert "tags" not in out
    assert out["title"] == "look at # tag"


def test_empty_input_falls_back_to_untitled():
    out = parse_local("")
    assert out["title"] == "Untitled"


def test_title_trimmed_and_collapsed():
    out = parse_local("   buy    milk   !high   ")
    assert out["title"] == "buy milk"
    assert out["priority"] == "high"


def test_title_truncated_to_200():
    out = parse_local("x" * 500)
    assert len(out["title"]) == 200


def test_only_tokens_keeps_original_as_title():
    out = parse_local("!high #x")
    # Title falls back to original input since stripping leaves nothing useful
    assert out["title"] == "!high #x"
    assert out["priority"] == "high"
    assert out["tags"] == ["x"]
