"""Todo router handling CRUD operations and statistics endpoints.

NOTE on route ordering: FastAPI matches routes in the order they are
declared. Every static-path endpoint (``/stats``, ``/summary``, ``/reorder``,
``/calendar.ics``, ``/ai-status``, ``/tags/list``) MUST be declared before
the parameterized ``/{todo_id}`` routes. Otherwise the router treats those
words as a todo id and returns 404 / 422.
"""

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from dependencies import get_current_user
from models import StreakStats, Todo, TodoCreate, TodoStats, TodoUpdate, User
from services import ai_service
from services.streak_service import compute_streak
from services.todo_service import TodoService
from store import JSONStore

# Initialize todo store and service
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
todo_store = JSONStore(os.path.join(DATA_DIR, "todos.json"))
todo_service = TodoService(todo_store)

router = APIRouter(prefix="/api/todos", tags=["todos"])


# --- Body schemas ---------------------------------------------------------


class ReorderBody(BaseModel):
    """Body for the manual reorder endpoint."""

    ordered_ids: list[str] = Field(default_factory=list)


class TimeBody(BaseModel):
    """Body for adding focus / Pomodoro time."""

    seconds: int = Field(ge=0)


class TagInfo(BaseModel):
    name: str
    count: int


class SubtaskSuggestion(BaseModel):
    title: str


class BulkActionRequest(BaseModel):
    """Body for the bulk-action endpoint."""

    ids: list[str] = Field(default_factory=list)
    action: str
    payload: dict | None = None


# --- Static-path endpoints (MUST come before /{todo_id} routes) -----------


@router.get("/stats", response_model=TodoStats)
async def get_stats(current_user: User = Depends(get_current_user)) -> TodoStats:
    """Get dashboard statistics for the authenticated user."""
    return todo_service.get_stats(current_user.id)


@router.get("/streak", response_model=StreakStats)
async def get_streak(current_user: User = Depends(get_current_user)) -> StreakStats:
    """Return completion-streak stats for the authenticated user."""
    records = [
        r for r in todo_service.todo_store.read_all() if r.get("user_id") == current_user.id
    ]
    return StreakStats(**compute_streak(records))


@router.get("/tags/list", response_model=list[TagInfo])
async def list_tags(current_user: User = Depends(get_current_user)) -> list[dict]:
    """Distinct tags used by the user with usage counts."""
    return todo_service.list_tags(current_user.id)


@router.post("/bulk")
async def bulk_action(
    body: BulkActionRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Apply ``body.action`` across ``body.ids`` in a single atomic write."""
    # Lazy import to avoid circular import (folders depends on todos)
    from routers.folders import folder_store

    return todo_service.bulk_action(
        user_id=current_user.id,
        ids=body.ids,
        action=body.action,
        payload=body.payload,
        folder_store=folder_store,
    )


@router.post("/reorder", response_model=list[Todo])
async def reorder(
    body: ReorderBody,
    current_user: User = Depends(get_current_user),
) -> list[Todo]:
    """Persist a manual ordering for the user's todos."""
    return todo_service.reorder(current_user.id, body.ordered_ids)


@router.get("/ai-status")
async def ai_status() -> dict:
    """Tell the frontend whether AI features are wired up."""
    return {"enabled": ai_service.is_enabled()}


@router.get("/calendar.ics", response_class=PlainTextResponse)
async def calendar_ics(current_user: User = Depends(get_current_user)) -> PlainTextResponse:
    """Export the user's todos as an .ics calendar feed.

    Each todo with a ``due_date`` becomes an all-day VEVENT. ``reminder_at``
    becomes a ``VALARM`` trigger inside that event.
    """
    todos = todo_service.list_todos(user_id=current_user.id)
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Todo App//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for todo in todos:
        if not todo.due_date:
            continue
        try:
            d = datetime.strptime(todo.due_date, "%Y-%m-%d")
        except ValueError:
            continue
        end = d.replace(day=d.day)
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{todo.id}@todo-app",
                f"DTSTAMP:{now_stamp}",
                f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}",
                f"SUMMARY:{_ics_escape(todo.title)}",
                f"DESCRIPTION:{_ics_escape(todo.description or '')}",
                f"STATUS:{'COMPLETED' if todo.status.value == 'done' else 'NEEDS-ACTION'}",
            ]
        )
        if todo.reminder_at:
            lines.extend(
                [
                    "BEGIN:VALARM",
                    "ACTION:DISPLAY",
                    f"DESCRIPTION:{_ics_escape(todo.title)}",
                    f"TRIGGER;VALUE=DATE-TIME:{todo.reminder_at.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
                    "END:VALARM",
                ]
            )
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")

    body = "\r\n".join(lines) + "\r\n"
    headers = {"Content-Disposition": 'attachment; filename="todos.ics"'}
    return PlainTextResponse(content=body, media_type="text/calendar", headers=headers)


@router.get("/summary")
async def summary(current_user: User = Depends(get_current_user)) -> dict:
    """AI-augmented summary of the user's todos.

    Falls back to a deterministic local summary when the OpenAI key isn't
    configured.
    """
    todos = todo_service.list_todos(user_id=current_user.id)
    stats = todo_service.get_stats(current_user.id)

    today = datetime.now(timezone.utc).date()
    upcoming = sorted(
        (
            t
            for t in todos
            if t.due_date
            and t.status.value != "done"
            and datetime.strptime(t.due_date, "%Y-%m-%d").date() >= today
        ),
        key=lambda t: t.due_date or "",
    )
    next_due = upcoming[0] if upcoming else None

    tag_counts = todo_service.list_tags(current_user.id)
    top_tags = tag_counts[:3]

    high_priority_pending = [
        t for t in todos if t.priority.value == "high" and t.status.value != "done"
    ]

    parts: list[str] = []
    parts.append(
        f"You have {stats.total} todo{'s' if stats.total != 1 else ''} "
        f"({stats.completed} done, {stats.pending} active)."
    )
    if stats.overdue:
        parts.append(f"{stats.overdue} are overdue — handle these first.")
    if high_priority_pending:
        focus_titles = ", ".join(t.title for t in high_priority_pending[:3])
        parts.append(f"High-priority focus: {focus_titles}.")
    if next_due:
        parts.append(f"Next up: \"{next_due.title}\" due {next_due.due_date}.")
    if top_tags:
        tag_summary = ", ".join(f"#{t['name']} ({t['count']})" for t in top_tags)
        parts.append(f"Top tags: {tag_summary}.")
    if not parts[1:]:
        parts.append("Nothing is overdue. Nice work staying on top of it.")

    deterministic = " ".join(parts)
    todo_dicts = [t.model_dump() for t in todos]
    folders: list[dict] = []
    try:
        from routers.folders import folder_service

        folders = [
            f.model_dump() for f in folder_service.list_for_user(current_user.id)
        ]
    except Exception:  # pragma: no cover - defensive
        folders = []

    ai_summary = ai_service.smart_summary(
        todos=todo_dicts,
        folders=folders,
        fallback=deterministic,
    )

    return {
        "stats": stats.model_dump(),
        "next_due_id": next_due.id if next_due else None,
        "next_due_title": next_due.title if next_due else None,
        "next_due_date": next_due.due_date if next_due else None,
        "high_priority_pending_ids": [t.id for t in high_priority_pending],
        "top_tags": top_tags,
        "summary": ai_summary["summary"],
        "summary_source": ai_summary["source"],
    }


# --- Collection endpoints -------------------------------------------------


@router.get("", response_model=list[Todo])
async def list_todos(
    status: str | None = Query(default=None, description="Filter by status (pending, in-progress, done)"),
    priority: str | None = Query(default=None, description="Filter by priority (low, medium, high)"),
    sort_by: str | None = Query(default=None, description="Sort by field (due_date, created_at, position)"),
    tag: str | None = Query(default=None, description="Filter by tag (case-insensitive exact match)"),
    search: str | None = Query(default=None, description="Free-text search over title, description, tags"),
    folder_id: str | None = Query(default=None, description="Filter by folder id, or 'none' for unassigned"),
    recurrence: str | None = Query(default=None, description="Filter by recurrence cadence"),
    current_user: User = Depends(get_current_user),
) -> list[Todo]:
    """List todos for the authenticated user with optional filtering and sorting."""
    return todo_service.list_todos(
        user_id=current_user.id,
        status=status,
        priority=priority,
        sort_by=sort_by,
        tag=tag,
        search=search,
        folder_id=folder_id,
        recurrence=recurrence,
    )


@router.post("", response_model=Todo, status_code=201)
async def create_todo(
    todo_data: TodoCreate,
    current_user: User = Depends(get_current_user),
) -> Todo:
    """Create a new todo for the authenticated user."""
    return todo_service.create(user_id=current_user.id, data=todo_data)


# --- Per-todo endpoints (parameterized — declared LAST) -------------------

UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post("/{todo_id}/time", response_model=Todo)
async def add_time(
    todo_id: str,
    body: TimeBody,
    current_user: User = Depends(get_current_user),
) -> Todo:
    """Increment a todo's tracked focus time (Pomodoro) by ``seconds``."""
    return todo_service.add_time(current_user.id, todo_id, body.seconds)


@router.post("/{todo_id}/image", response_model=Todo)
async def upload_image(
    todo_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> Todo:
    """Attach an image to a todo. Replaces any existing image."""
    todo_service.get_by_id(current_user.id, todo_id)

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported image type")

    contents = await file.read()
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 5 MB)")

    extension = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }[file.content_type]
    filename = f"{uuid.uuid4().hex}{extension}"
    path = os.path.join(UPLOADS_DIR, filename)
    with open(path, "wb") as fh:
        fh.write(contents)

    image_url = f"/uploads/{filename}"
    return todo_service.set_image(current_user.id, todo_id, image_url)


@router.delete("/{todo_id}/image", response_model=Todo)
async def remove_image(
    todo_id: str,
    current_user: User = Depends(get_current_user),
) -> Todo:
    """Remove the image attached to a todo (if any)."""
    todo = todo_service.get_by_id(current_user.id, todo_id)
    if todo.image_url:
        rel = todo.image_url.lstrip("/")
        if rel.startswith("uploads/"):
            file_path = os.path.join(UPLOADS_DIR, os.path.basename(rel))
            if os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except OSError:
                    pass
    return todo_service.set_image(current_user.id, todo_id, None)


@router.post("/{todo_id}/suggest-subtasks", response_model=list[SubtaskSuggestion])
async def suggest_subtasks(
    todo_id: str,
    current_user: User = Depends(get_current_user),
) -> list[SubtaskSuggestion]:
    """Use the configured LLM to suggest 3-5 subtasks for a todo."""
    todo = todo_service.get_by_id(current_user.id, todo_id)
    suggestions = ai_service.suggest_subtasks(
        title=todo.title, description=todo.description
    )
    return [SubtaskSuggestion(title=s) for s in suggestions]


@router.get("/{todo_id}", response_model=Todo)
async def get_todo(
    todo_id: str,
    current_user: User = Depends(get_current_user),
) -> Todo:
    """Get a specific todo by ID."""
    return todo_service.get_by_id(user_id=current_user.id, todo_id=todo_id)


@router.put("/{todo_id}", response_model=Todo)
async def update_todo(
    todo_id: str,
    todo_data: TodoUpdate,
    apply_to: str = Query(default="occurrence", description="occurrence | series"),
    current_user: User = Depends(get_current_user),
) -> Todo:
    """Update a specific todo by ID."""
    return todo_service.update(
        user_id=current_user.id,
        todo_id=todo_id,
        data=todo_data,
        apply_to=apply_to,
    )


@router.delete("/{todo_id}", status_code=204)
async def delete_todo(
    todo_id: str,
    apply_to: str = Query(default="occurrence", description="occurrence | series"),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a specific todo by ID."""
    todo_service.delete(user_id=current_user.id, todo_id=todo_id, apply_to=apply_to)
    return Response(status_code=204)


# --- Helpers --------------------------------------------------------------


def _ics_escape(text: str) -> str:
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )
