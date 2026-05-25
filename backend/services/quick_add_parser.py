"""Deterministic local parser for natural-language todo quick-add.

Used when OPENAI_API_KEY is missing or the model call fails. The grammar is
intentionally narrow and predictable; anything we can't classify becomes
part of the title. The parser never raises.

Tokens (anywhere in the input):
    !high | !med | !medium | !low      -> priority
    #tag                                -> tags  (lowercased, deduped)
    @YYYY-MM-DD                         -> due_date
    every day|week|month|year           -> recurrence  (consumes both words)

Remaining whitespace-trimmed text becomes the title. If no text remains we
fall back to the original input as the title so the caller always gets one.
"""

from __future__ import annotations

import re

_PRIORITY_TOKEN = re.compile(r"(?<!\S)!(high|med|medium|low)(?!\S)", re.IGNORECASE)
_TAG_TOKEN = re.compile(r"(?<!\S)#([A-Za-z0-9_-]{1,32})")
_DATE_TOKEN = re.compile(r"(?<!\S)@(\d{4}-\d{2}-\d{2})(?!\S)")
_RECURRENCE_TOKEN = re.compile(r"(?<!\S)every\s+(day|week|month|year)\b", re.IGNORECASE)

_PRIORITY_MAP = {"high": "high", "med": "medium", "medium": "medium", "low": "low"}
_RECURRENCE_MAP = {
    "day": "daily",
    "week": "weekly",
    "month": "monthly",
    "year": "yearly",
}


def parse_local(text: str) -> dict:
    """Parse ``text`` into a partial todo dict. Never raises."""
    raw = text or ""
    result: dict = {}
    tags: list[str] = []
    remaining = raw

    m = _PRIORITY_TOKEN.search(remaining)
    if m:
        result["priority"] = _PRIORITY_MAP[m.group(1).lower()]
        remaining = remaining[: m.start()] + remaining[m.end() :]

    m = _DATE_TOKEN.search(remaining)
    if m:
        result["due_date"] = m.group(1)
        remaining = remaining[: m.start()] + remaining[m.end() :]

    m = _RECURRENCE_TOKEN.search(remaining)
    if m:
        result["recurrence"] = _RECURRENCE_MAP[m.group(1).lower()]
        remaining = remaining[: m.start()] + remaining[m.end() :]

    # Tags can appear multiple times; collect them all
    while True:
        m = _TAG_TOKEN.search(remaining)
        if not m:
            break
        tag = m.group(1).lower()
        if tag not in tags:
            tags.append(tag)
        remaining = remaining[: m.start()] + remaining[m.end() :]

    if tags:
        result["tags"] = tags

    title = " ".join(remaining.split()).strip()
    if not title:
        title = raw.strip() or "Untitled"
    result["title"] = title[:200]
    return result
