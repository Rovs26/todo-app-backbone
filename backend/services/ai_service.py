"""AI helpers powered by OpenAI when an API key is configured.

The service is intentionally tolerant: when no key is present, calls return a
deterministic local fallback so the app remains fully usable.

The API key is read from ``OPENAI_API_KEY`` (loaded from .env or .env.local
via python-dotenv at process startup).
"""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from typing import Any

try:  # python-dotenv is optional in tests
    from dotenv import load_dotenv
    from pathlib import Path

    # Look for .env files starting at the repo root (parent of backend/) so
    # the same .env.local works regardless of which directory uvicorn was
    # launched from.
    _here = Path(__file__).resolve()
    _candidates = [
        _here.parents[2] / ".env",       # repo root .env
        _here.parents[2] / ".env.local", # repo root .env.local (overrides)
        _here.parents[1] / ".env",       # backend/.env
        _here.parents[1] / ".env.local", # backend/.env.local
    ]
    for _path in _candidates:
        if _path.exists():
            load_dotenv(_path, override=True)
except Exception:  # pragma: no cover
    pass

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


_DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def is_enabled() -> bool:
    return bool(os.getenv("OPENAI_API_KEY")) and OpenAI is not None


def _client() -> Any | None:
    if not is_enabled():
        return None
    try:
        return OpenAI()
    except Exception:
        return None


def _todo_brief(todo: dict) -> dict:
    """Reduce a todo to the small set of fields we send to the model."""
    return {
        "title": todo.get("title"),
        "status": todo.get("status"),
        "priority": todo.get("priority"),
        "due_date": todo.get("due_date"),
        "tags": todo.get("tags") or [],
        "folder_id": todo.get("folder_id"),
    }


def smart_summary(
    *,
    todos: list[dict],
    folders: list[dict],
    fallback: str,
) -> dict:
    """Generate a natural-language summary of the user's todos.

    Falls back to ``fallback`` (the deterministic summary) when no OpenAI key
    is configured or the call fails.
    """
    client = _client()
    if not client:
        return {"summary": fallback, "source": "local"}

    payload = {
        "now_iso": datetime.now(timezone.utc).isoformat(),
        "folders": [{"id": f.get("id"), "name": f.get("name")} for f in folders],
        "todos": [_todo_brief(t) for t in todos[:80]],
    }

    try:
        response = client.chat.completions.create(
            model=_DEFAULT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise productivity coach. Given the user's "
                        "todos, write a 2-4 sentence summary that calls out the "
                        "most urgent or impactful next steps. Mention specific "
                        "todo titles when helpful. No bullet lists, no headings, "
                        "no questions."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
            temperature=0.4,
            max_tokens=180,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            return {"summary": fallback, "source": "local"}
        return {"summary": text, "source": "openai"}
    except Exception as exc:  # pragma: no cover - network / quota issues
        return {
            "summary": fallback,
            "source": "local",
            "error": str(exc),
        }


def suggest_subtasks(*, title: str, description: str | None) -> list[str]:
    """Ask the model to break a todo into 3-5 actionable subtasks."""
    client = _client()
    if not client:
        return []

    try:
        response = client.chat.completions.create(
            model=_DEFAULT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You convert a user task into 3 to 5 short, concrete, "
                        "ordered subtasks. Reply ONLY with a JSON array of "
                        "strings. No prose, no markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"title": title, "description": description or ""},
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0.3,
            max_tokens=200,
        )
        raw = (response.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            # remove leading "json\n" if any
            if raw.lower().startswith("json"):
                raw = raw[4:].lstrip()
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()][:5]
        return []
    except Exception:  # pragma: no cover
        return []


def coach_message(
    *,
    todos: list[dict],
    folders: list[dict],
) -> str | None:
    """Generate a short proactive nudge for the user.

    Used by the "AI notifications" feature. Returns ``None`` when no nudge is
    appropriate or when the API is unavailable.
    """
    client = _client()
    if not client:
        return None

    pending = [t for t in todos if t.get("status") != "done"]
    if not pending:
        return None

    payload = {
        "now_iso": datetime.now(timezone.utc).isoformat(),
        "folders": [{"id": f.get("id"), "name": f.get("name")} for f in folders],
        "todos": [_todo_brief(t) for t in pending[:60]],
    }

    try:
        response = client.chat.completions.create(
            model=_DEFAULT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a friendly, brief productivity coach. Look at "
                        "the user's open todos and surface ONE actionable nudge "
                        "in a single short sentence. Mention specific titles "
                        "when helpful. Plain text, no markdown, no questions."
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.5,
            max_tokens=80,
        )
        text = (response.choices[0].message.content or "").strip()
        return text or None
    except Exception:  # pragma: no cover
        return None


_PARSE_TODO_SCHEMA = {
    "name": "parsed_todo",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string", "minLength": 1, "maxLength": 200},
            "description": {"type": ["string", "null"], "maxLength": 2000},
            "priority": {"type": ["string", "null"], "enum": ["low", "medium", "high", None]},
            "due_date": {"type": ["string", "null"]},
            "reminder_at": {"type": ["string", "null"]},
            "recurrence": {
                "type": ["string", "null"],
                "enum": ["none", "daily", "weekly", "monthly", "yearly", None],
            },
            "tags": {"type": ["array", "null"], "items": {"type": "string"}},
            "folder_id": {"type": ["string", "null"]},
            "subtasks": {"type": ["array", "null"], "items": {"type": "string"}},
        },
        "required": ["title"],
    },
}


def parse_todo(text: str, folders: list[dict]) -> dict:
    """Parse a natural-language phrase into structured todo fields.

    Returns ``{"data": dict, "source": "openai"|"local", "error"?: str}``.

    The OpenAI call is forced to follow ``_PARSE_TODO_SCHEMA`` via
    ``response_format={"type":"json_schema", ...}``. Callers always get a
    ``title`` (the schema requires it). When the model is unavailable or the
    call errors, the deterministic local parser handles the input.
    """
    from services.quick_add_parser import parse_local  # local import to avoid cycle

    client = _client()
    if not client:
        return {"data": parse_local(text), "source": "local"}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder_pairs = [
        {"id": f.get("id"), "name": f.get("name")}
        for f in folders
        if f.get("id") and f.get("name")
    ]
    system = (
        "You extract structured todo fields from a single natural-language "
        "phrase. Respond ONLY with the JSON object — no commentary.\n"
        f"Today (UTC) is {today}. Resolve relative dates to a YYYY-MM-DD `due_date`: "
        f"'tomorrow', 'next Friday', 'in 3 days'. Vague time words like "
        f"'later', 'later today', 'today', 'tonight', 'this evening', "
        f"'this afternoon', 'this morning' also resolve to today ({today}). "
        "Resolve clock-specific phrases like 'remind me at 9am tomorrow' to "
        "an ISO 8601 `reminder_at`. "
        "If the phrase lists distinct items to buy, do, or collect (e.g. "
        "'buy milk, eggs and bread' or 'pick up A, B, and C'), extract each "
        "item as an element of `subtasks` (short strings, no leading verbs). "
        "Recognize !high|!med|!low and #tag inline tokens. "
        "If the phrase mentions one of the user's folders by name, set "
        "`folder_id` to that folder's id. Otherwise leave it null. "
        "Recurrence values are exactly: none, daily, weekly, monthly, yearly."
    )
    user_payload = {
        "text": text,
        "folders": folder_pairs,
    }
    try:
        response = client.chat.completions.create(
            model=_DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_schema", "json_schema": _PARSE_TODO_SCHEMA},
            temperature=0.1,
            max_tokens=400,
        )
        raw = (response.choices[0].message.content or "").strip()
        parsed = json.loads(raw) if raw else {}
        if not isinstance(parsed, dict) or not parsed.get("title"):
            return {"data": parse_local(text), "source": "local"}
        return {"data": parsed, "source": "openai"}
    except Exception as exc:
        return {
            "data": parse_local(text),
            "source": "local",
            "error": type(exc).__name__,
        }


_PARSE_IMAGE_SCHEMA = {
    "name": "image_todos",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string", "minLength": 1, "maxLength": 200},
                        "priority": {
                            "type": ["string", "null"],
                            "enum": ["low", "medium", "high", None],
                        },
                        "due_date": {"type": ["string", "null"]},
                        "tags": {
                            "type": ["array", "null"],
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["title"],
                },
            },
        },
        "required": ["items"],
    },
}


_PARSE_IMAGE_MAX_ITEMS = 30


def parse_image(image_bytes: bytes, mime: str, *, model: str | None = None) -> dict:
    """Extract a list of todo candidates from a photo of a written/whiteboard list.

    Returns ``{"items": list[dict]}`` on success, raises ``RuntimeError`` if
    AI is unavailable or the call fails. Items are capped at
    ``_PARSE_IMAGE_MAX_ITEMS`` (Requirement 1.7).
    """
    client = _client()
    if not client:
        raise RuntimeError("ai_unavailable")

    use_model = model or os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    system = (
        "You extract a list of actionable to-do items from a photo of a "
        "handwritten list, whiteboard, sticky-notes, or printed checklist. "
        "Return ONLY the JSON object described by the schema. "
        "Each item's title should be one short imperative phrase (1-12 words). "
        "Skip headers, dates, and decorative text. If you cannot find clear "
        "items, return an empty `items` array."
    )

    try:
        response = client.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract todos from this image."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            response_format={"type": "json_schema", "json_schema": _PARSE_IMAGE_SCHEMA},
            temperature=0.1,
            max_tokens=1500,
        )
    except Exception as exc:
        raise RuntimeError(type(exc).__name__) from exc

    raw = (response.choices[0].message.content or "").strip()
    try:
        parsed = json.loads(raw) if raw else {"items": []}
    except json.JSONDecodeError as exc:
        raise RuntimeError("JSONDecodeError") from exc

    items = parsed.get("items") if isinstance(parsed, dict) else None
    if not isinstance(items, list):
        items = []
    cleaned: list[dict] = []
    for item in items[:_PARSE_IMAGE_MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        if not title:
            continue
        out: dict = {"title": title[:200]}
        pri = item.get("priority")
        if pri in ("low", "medium", "high"):
            out["priority"] = pri
        due = item.get("due_date")
        if isinstance(due, str) and due:
            out["due_date"] = due
        tags = item.get("tags")
        if isinstance(tags, list):
            clean_tags = [str(t).strip().lower() for t in tags if str(t).strip()]
            if clean_tags:
                out["tags"] = clean_tags
        cleaned.append(out)
    return {"items": cleaned}


def transcribe_audio(file_bytes: bytes, filename: str) -> str | None:
    """Transcribe audio bytes via Whisper. Returns ``None`` on failure."""
    client = _client()
    if not client:
        return None
    try:
        # The OpenAI SDK accepts a (filename, bytes) tuple as the file argument.
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=(filename or "audio.webm", file_bytes),
        )
        text = (getattr(result, "text", "") or "").strip()
        return text or None
    except Exception:  # pragma: no cover
        return None


def chat(
    *,
    user_message: str,
    history: list[dict],
    todos: list[dict],
    folders: list[dict],
    weather: dict | None = None,
) -> str | None:
    """Conversational assistant grounded in the user's todos.

    ``history`` is a list of ``{"role": "user"|"assistant", "content": str}``
    entries representing prior turns of the same conversation. ``weather`` is
    an optional snapshot (current + ``forecast`` list) supplied by the
    frontend via Open-Meteo; when present the assistant can answer questions
    about today/tomorrow's weather instead of refusing. Returns ``None`` when
    AI is unavailable.
    """
    client = _client()
    if not client:
        return None

    context = {
        "now_iso": datetime.now(timezone.utc).isoformat(),
        "folders": [
            {"id": f.get("id"), "name": f.get("name")} for f in folders
        ],
        "todos": [
            dict(_todo_brief(t), id=t.get("id")) for t in todos[:80]
        ],
    }
    if weather:
        context["weather"] = weather

    weather_clause = (
        " If a `weather` object is present in the JSON it contains real "
        "Open-Meteo data for the user's location, including a `forecast` "
        "array keyed by date — use it to answer weather questions (today, "
        "tomorrow, day after) instead of refusing."
        if weather
        else ""
    )

    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are a concise, helpful assistant inside a personal todo "
                "app. The user's current todos and folders are provided as "
                "JSON in the next message. Use that context when answering. "
                "Keep replies short (2-4 sentences). Reference todos by their "
                "title in quotes when useful. No markdown headings."
                + weather_clause
            ),
        },
        {
            "role": "system",
            "content": "USER_CONTEXT_JSON: " + json.dumps(context, ensure_ascii=False),
        },
    ]
    for turn in history[-10:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model=_DEFAULT_MODEL,
            messages=messages,
            temperature=0.4,
            max_tokens=300,
        )
        text = (response.choices[0].message.content or "").strip()
        return text or None
    except Exception:  # pragma: no cover
        return None
