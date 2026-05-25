"""Voice agent: plan + apply natural-language commands as structured actions.

The planner asks the model to emit OpenAI tool calls; we transform those
into a typed action list. The apply step runs each action through the
existing service layer in order, stopping at the first failure.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from models import CommentCreate, FolderCreate, Priority, TodoCreate, TodoUpdate
from services import ai_service


_MAX_ACTIONS = 20
_ALLOWED_TOOLS = {
    "create_folder",
    "create_todo",
    "add_comment",
    "mark_done",
    "set_priority",
}

_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Create a new folder/category for the user.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 80},
                    "color": {"type": ["string", "null"]},
                    "icon": {"type": ["string", "null"]},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_todo",
            "description": (
                "Create a new todo. Use folder_name if you only know the "
                "folder by name; the server resolves to folder_id."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string", "minLength": 1, "maxLength": 200},
                    "folder_id": {"type": ["string", "null"]},
                    "folder_name": {"type": ["string", "null"]},
                    "priority": {
                        "type": ["string", "null"],
                        "enum": ["low", "medium", "high", None],
                    },
                    "due_date": {"type": ["string", "null"]},
                    "reminder_at": {"type": ["string", "null"]},
                    "recurrence": {
                        "type": ["string", "null"],
                        "enum": ["none", "daily", "weekly", "monthly", "yearly", None],
                    },
                    "tags": {
                        "type": ["array", "null"],
                        "items": {"type": "string"},
                    },
                    "subtasks": {
                        "type": ["array", "null"],
                        "items": {"type": "string"},
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_comment",
            "description": "Add a comment to a todo. Use todo_title if id is unknown.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "todo_id": {"type": ["string", "null"]},
                    "todo_title": {"type": ["string", "null"]},
                    "body": {"type": "string", "minLength": 1, "maxLength": 2000},
                },
                "required": ["body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_done",
            "description": "Mark a todo as done.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "todo_id": {"type": ["string", "null"]},
                    "todo_title": {"type": ["string", "null"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_priority",
            "description": "Change a todo's priority.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "todo_id": {"type": ["string", "null"]},
                    "todo_title": {"type": ["string", "null"]},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["priority"],
            },
        },
    },
]


def _resolve_folder_id(name: str | None, folders: list[dict]) -> str | None:
    if not name:
        return None
    needle = name.strip().lower()
    if not needle:
        return None
    for f in folders:
        if (f.get("name") or "").strip().lower() == needle:
            return f.get("id")
    return None


def _resolve_todo_id(
    title: str | None, todos: list[dict], todo_id: str | None = None
) -> str | None:
    if todo_id:
        return todo_id
    if not title:
        return None
    needle = title.strip().lower()
    if not needle:
        return None
    matches: list[dict] = []
    for t in todos:
        if needle in (t.get("title") or "").strip().lower():
            matches.append(t)
    if not matches:
        return None
    matches.sort(key=lambda r: r.get("updated_at") or r.get("created_at") or "", reverse=True)
    return matches[0].get("id")


def _normalize_actions(
    raw: list[dict],
    folders: list[dict],
    todos: list[dict],
) -> list[dict]:
    """Resolve folder_name/todo_title to ids; drop unknown/invalid actions."""
    out: list[dict] = []
    for entry in raw[:_MAX_ACTIONS]:
        name = entry.get("name")
        args = entry.get("arguments") or {}
        if name not in _ALLOWED_TOOLS or not isinstance(args, dict):
            continue
        action: dict = {"name": name, "arguments": dict(args)}
        if name == "create_todo":
            fid = args.get("folder_id") or _resolve_folder_id(
                args.get("folder_name"), folders
            )
            action["resolved_folder_id"] = fid
        elif name in {"add_comment", "mark_done", "set_priority"}:
            tid = _resolve_todo_id(args.get("todo_title"), todos, args.get("todo_id"))
            action["resolved_todo_id"] = tid
        out.append(action)
    return out


def plan(
    *,
    transcript: str,
    folders: list[dict],
    todos: list[dict],
) -> dict:
    """Ask the model to translate the transcript into a list of actions.

    Returns ``{"actions": list[dict], "assistant_reply": str}``. Raises
    ``RuntimeError`` if the AI backend is unavailable or the call fails.
    """
    client = ai_service._client()
    if not client:
        raise RuntimeError("ai_unavailable")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    system = (
        "You translate a user's spoken request into one or more structured "
        "actions for a personal todo app. Emit ONE tool call per action; do "
        "not chat in prose unless there is nothing actionable. "
        f"Today (UTC) is {today}. Resolve relative dates to YYYY-MM-DD. "
        "If the user mentions a folder by name, prefer setting `folder_name`; "
        "the server resolves it. Recurrence values: none|daily|weekly|monthly|yearly."
    )
    context_payload = {
        "folders": [{"id": f.get("id"), "name": f.get("name")} for f in folders],
        "recent_todos": [
            {
                "id": t.get("id"),
                "title": t.get("title"),
                "status": t.get("status"),
                "priority": t.get("priority"),
            }
            for t in todos[:20]
        ],
    }

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "system",
                    "content": "USER_CONTEXT_JSON: "
                    + json.dumps(context_payload, ensure_ascii=False),
                },
                {"role": "user", "content": transcript},
            ],
            tools=_TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.2,
            max_tokens=800,
        )
    except Exception as exc:
        raise RuntimeError(type(exc).__name__) from exc

    choice = response.choices[0]
    message = choice.message
    raw_actions: list[dict] = []
    for tc in getattr(message, "tool_calls", None) or []:
        fn = getattr(tc, "function", None)
        if not fn:
            continue
        try:
            args = json.loads(fn.arguments) if fn.arguments else {}
        except (json.JSONDecodeError, TypeError):
            continue
        raw_actions.append({"name": fn.name, "arguments": args})

    actions = _normalize_actions(raw_actions, folders, todos)
    reply = (getattr(message, "content", None) or "").strip()
    if not reply:
        reply = (
            f"I planned {len(actions)} action{'s' if len(actions) != 1 else ''}. "
            "Review and apply."
            if actions
            else "I didn't catch an actionable request."
        )
    return {"actions": actions, "assistant_reply": reply}


# --- Apply ------------------------------------------------------------------


def apply(
    *,
    user_id: str,
    actions: list[dict],
    folder_service: Any,
    todo_service: Any,
    comment_service: Any,
) -> dict:
    """Execute actions in order; stop at the first failure.

    Returns ``{"applied": [...], "failed": {...}|None, "remaining": [...]}``.
    """
    applied: list[dict] = []
    failed: dict | None = None
    remaining: list[dict] = []

    # Local cache of folder name -> id for multi-step apply (Requirement 2.3):
    # if a create_folder happens earlier in the batch, a later create_todo can
    # reference it by name.
    folder_name_to_id: dict[str, str] = {}

    for idx, action in enumerate(actions[:_MAX_ACTIONS]):
        name = action.get("name")
        args = action.get("arguments") or {}
        try:
            if name == "create_folder":
                folder = folder_service.create(
                    user_id, FolderCreate(**_clean_dict(args, {"name", "color", "icon"}))
                )
                folder_name_to_id[(args.get("name") or "").strip().lower()] = folder.id
                applied.append({"index": idx, "name": name, "result": folder.model_dump(mode="json")})
            elif name == "create_todo":
                fid = action.get("resolved_folder_id") or args.get("folder_id")
                if not fid and args.get("folder_name"):
                    fid = folder_name_to_id.get(args["folder_name"].strip().lower())
                payload = _clean_dict(
                    args,
                    {
                        "title", "priority", "due_date", "reminder_at",
                        "recurrence", "tags",
                    },
                )
                if fid:
                    payload["folder_id"] = fid
                if isinstance(args.get("subtasks"), list):
                    payload["subtasks"] = [
                        {"id": f"sub-{i}", "title": str(s).strip(), "done": False}
                        for i, s in enumerate(args["subtasks"])
                        if str(s).strip()
                    ]
                todo = todo_service.create(user_id, TodoCreate(**payload))
                applied.append({"index": idx, "name": name, "result": todo.model_dump(mode="json")})
            elif name == "add_comment":
                tid = action.get("resolved_todo_id") or args.get("todo_id")
                if not tid:
                    raise ValueError("could_not_resolve_todo")
                comment = comment_service.create_comment(
                    user_id, tid, CommentCreate(body=args.get("body") or "")
                )
                applied.append({"index": idx, "name": name, "result": comment.model_dump(mode="json")})
            elif name == "mark_done":
                tid = action.get("resolved_todo_id") or args.get("todo_id")
                if not tid:
                    raise ValueError("could_not_resolve_todo")
                todo = todo_service.update(user_id, tid, TodoUpdate(status="done"))
                applied.append({"index": idx, "name": name, "result": todo.model_dump(mode="json")})
            elif name == "set_priority":
                tid = action.get("resolved_todo_id") or args.get("todo_id")
                if not tid:
                    raise ValueError("could_not_resolve_todo")
                pri = args.get("priority")
                if pri not in {"low", "medium", "high"}:
                    raise ValueError("invalid_priority")
                todo = todo_service.update(user_id, tid, TodoUpdate(priority=Priority(pri)))
                applied.append({"index": idx, "name": name, "result": todo.model_dump(mode="json")})
            else:
                raise ValueError(f"unknown_action:{name}")
        except Exception as exc:
            failed = {
                "index": idx,
                "action": action,
                "error_class": type(exc).__name__,
                "error_message": str(exc)[:500],
            }
            remaining = list(actions[idx + 1 :])
            break

    return {"applied": applied, "failed": failed, "remaining": remaining}


def _clean_dict(d: dict, keys: set[str]) -> dict:
    out: dict = {}
    for k in keys:
        if k in d and d[k] not in (None, ""):
            out[k] = d[k]
    return out
