"""SQLAlchemy ORM models mirroring the Pydantic shapes in ``models.py``.

Each ``*Row`` class is keyed by ``id`` (text PK) and exposes ``to_dict()``
and ``from_dict()`` so the ``SQLStore`` adapter can mediate between dicts
(JSONStore's currency) and ORM rows.

List/dict-typed fields (tags, subtasks, comments, mentions) are stored
in JSON-encoded TEXT columns per Requirement 1.2 of the migration spec.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


# --- Helpers ---------------------------------------------------------------


def _dump_json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, default=str)


def _load_json(value: str | None, default: Any) -> Any:
    if value is None or value == "":
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


# --- Users -----------------------------------------------------------------


class UserRow(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    email_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "password_hash": self.password_hash,
            "created_at": self.created_at,
            "email_reminders_enabled": self.email_reminders_enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserRow":
        return cls(
            id=data["id"],
            email=data.get("email", ""),
            username=data.get("username", ""),
            password_hash=data.get("password_hash", ""),
            created_at=_iso(data.get("created_at")),
            email_reminders_enabled=bool(data.get("email_reminders_enabled", True)),
        )

    def update_from_dict(self, updates: dict) -> None:
        for k, v in updates.items():
            if k == "id":
                continue
            if k == "created_at":
                self.created_at = _iso(v)
            elif hasattr(self, k):
                setattr(self, k, v)


# --- Folders ---------------------------------------------------------------


class FolderRow(Base):
    __tablename__ = "folders"
    __table_args__ = (Index("ix_folders_user_id", "user_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    color: Mapped[str | None] = mapped_column(String, nullable=True)
    icon: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str | None] = mapped_column(String, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "color": self.color,
            "icon": self.icon,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FolderRow":
        return cls(
            id=data["id"],
            user_id=data.get("user_id", ""),
            name=data.get("name", ""),
            color=data.get("color"),
            icon=data.get("icon"),
            created_at=_iso(data.get("created_at")),
            updated_at=_iso(data.get("updated_at")) if data.get("updated_at") else None,
        )

    def update_from_dict(self, updates: dict) -> None:
        for k, v in updates.items():
            if k == "id":
                continue
            if k in {"created_at", "updated_at"} and v is not None:
                v = _iso(v)
            if hasattr(self, k):
                setattr(self, k, v)


# --- Todos -----------------------------------------------------------------


# Columns we promote to real (filterable, indexable) columns; everything
# else round-trips through the ``extra`` JSON blob. Lists/dicts live in
# dedicated JSON-text columns so they survive round-trips.
_TODO_SCALAR_FIELDS = {
    "id", "user_id", "title", "description", "priority", "due_date",
    "reminder_at", "reminder_sent", "reminder_sent_at", "status",
    "folder_id", "image_url", "position", "time_spent_seconds",
    "recurrence", "recurrence_until", "recurrence_count",
    "recurrence_series_id", "recurrence_index", "created_at", "updated_at",
}
_TODO_LIST_FIELDS = {"tags", "subtasks", "comments"}


class TodoRow(Base):
    __tablename__ = "todos"
    __table_args__ = (
        Index("ix_todos_user_id", "user_id"),
        Index("ix_todos_folder_id", "folder_id"),
        Index("ix_todos_status", "status"),
        Index("ix_todos_series", "recurrence_series_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String, default="medium", nullable=False)
    due_date: Mapped[str | None] = mapped_column(String, nullable=True)
    reminder_at: Mapped[str | None] = mapped_column(String, nullable=True)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reminder_sent_at: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    folder_id: Mapped[str | None] = mapped_column(String, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recurrence: Mapped[str] = mapped_column(String, default="none", nullable=False)
    recurrence_until: Mapped[str | None] = mapped_column(String, nullable=True)
    recurrence_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recurrence_series_id: Mapped[str | None] = mapped_column(String, nullable=True)
    recurrence_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str | None] = mapped_column(String, nullable=True)
    # JSON-text columns for nested lists.
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    subtasks_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    comments_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    # Forward-compatibility for any non-promoted scalar fields.
    extra_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    def to_dict(self) -> dict:
        out: dict = {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "due_date": self.due_date,
            "reminder_at": self.reminder_at,
            "reminder_sent": bool(self.reminder_sent),
            "reminder_sent_at": self.reminder_sent_at,
            "status": self.status,
            "folder_id": self.folder_id,
            "image_url": self.image_url,
            "position": int(self.position or 0),
            "time_spent_seconds": int(self.time_spent_seconds or 0),
            "recurrence": self.recurrence or "none",
            "recurrence_until": self.recurrence_until,
            "recurrence_count": self.recurrence_count,
            "recurrence_series_id": self.recurrence_series_id,
            "recurrence_index": int(self.recurrence_index or 0),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": _load_json(self.tags_json, []),
            "subtasks": _load_json(self.subtasks_json, []),
            "comments": _load_json(self.comments_json, []),
        }
        extra = _load_json(self.extra_json, {})
        if isinstance(extra, dict):
            for k, v in extra.items():
                out.setdefault(k, v)
        return out

    @classmethod
    def from_dict(cls, data: dict) -> "TodoRow":
        row = cls(id=data["id"])
        row.update_from_dict(data)
        return row

    def update_from_dict(self, updates: dict) -> None:
        # Lists -> JSON columns.
        for list_field in _TODO_LIST_FIELDS:
            if list_field in updates:
                setattr(self, f"{list_field}_json", _dump_json(updates[list_field] or []))
        # Scalars -> direct columns.
        for k, v in updates.items():
            if k in _TODO_LIST_FIELDS or k == "id":
                continue
            if k in _TODO_SCALAR_FIELDS:
                if k in {"created_at", "updated_at", "reminder_at", "reminder_sent_at"}:
                    v = _iso(v) if v is not None else None
                setattr(self, k, v)
        # Anything not promoted goes into extra_json (merge with existing).
        extra = _load_json(self.extra_json, {}) or {}
        for k, v in updates.items():
            if k in _TODO_SCALAR_FIELDS or k in _TODO_LIST_FIELDS or k == "id":
                continue
            extra[k] = v
        self.extra_json = _dump_json(extra) or "{}"


# --- Notifications ---------------------------------------------------------


class NotificationRow(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_id", "user_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    todo_id: Mapped[str | None] = mapped_column(String, nullable=True)
    todo_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_type: Mapped[str | None] = mapped_column(String, nullable=True)
    triggered_at: Mapped[str | None] = mapped_column(String, nullable=True)
    delivered_at: Mapped[str | None] = mapped_column(String, nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    _SCALARS = {
        "id", "user_id", "todo_id", "todo_title", "notification_type",
        "triggered_at", "delivered_at", "read",
    }

    def to_dict(self) -> dict:
        out = {
            "id": self.id,
            "user_id": self.user_id,
            "todo_id": self.todo_id,
            "todo_title": self.todo_title,
            "notification_type": self.notification_type,
            "triggered_at": self.triggered_at,
            "delivered_at": self.delivered_at,
            "read": bool(self.read),
        }
        extra = _load_json(self.extra_json, {})
        if isinstance(extra, dict):
            for k, v in extra.items():
                out.setdefault(k, v)
        return out

    @classmethod
    def from_dict(cls, data: dict) -> "NotificationRow":
        row = cls(id=data["id"])
        row.update_from_dict(data)
        return row

    def update_from_dict(self, updates: dict) -> None:
        for k, v in updates.items():
            if k == "id":
                continue
            if k in self._SCALARS:
                setattr(self, k, v)
        extra = _load_json(self.extra_json, {}) or {}
        for k, v in updates.items():
            if k in self._SCALARS or k == "id":
                continue
            extra[k] = v
        self.extra_json = _dump_json(extra) or "{}"


# --- Attachments -----------------------------------------------------------


class AttachmentRow(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        Index("ix_attachments_owner_id", "owner_id"),
        Index("ix_attachments_comment_id", "comment_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False)
    comment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    todo_id: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    original_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    _SCALARS = {
        "id", "owner_id", "comment_id", "todo_id", "url",
        "mime_type", "size_bytes", "original_name", "created_at",
    }

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "comment_id": self.comment_id,
            "todo_id": self.todo_id,
            "url": self.url,
            "mime_type": self.mime_type,
            "size_bytes": int(self.size_bytes or 0),
            "original_name": self.original_name,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AttachmentRow":
        row = cls(id=data["id"])
        row.update_from_dict(data)
        return row

    def update_from_dict(self, updates: dict) -> None:
        for k, v in updates.items():
            if k == "id":
                continue
            if k == "created_at" and v is not None:
                v = _iso(v)
            if k in self._SCALARS:
                setattr(self, k, v)


# --- Reminder send log -----------------------------------------------------


class ReminderLogRow(Base):
    __tablename__ = "reminder_send_log"
    __table_args__ = (Index("ix_reminder_log_user_id", "user_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    todo_id: Mapped[str | None] = mapped_column(String, nullable=True)
    sent_at: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    extra_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    _SCALARS = {"id", "user_id", "todo_id", "sent_at", "status"}

    def to_dict(self) -> dict:
        out = {
            "id": self.id,
            "user_id": self.user_id,
            "todo_id": self.todo_id,
            "sent_at": self.sent_at,
            "status": self.status,
        }
        extra = _load_json(self.extra_json, {})
        if isinstance(extra, dict):
            for k, v in extra.items():
                out.setdefault(k, v)
        return out

    @classmethod
    def from_dict(cls, data: dict) -> "ReminderLogRow":
        row = cls(id=data["id"])
        row.update_from_dict(data)
        return row

    def update_from_dict(self, updates: dict) -> None:
        for k, v in updates.items():
            if k == "id":
                continue
            if k in self._SCALARS:
                setattr(self, k, v)
        extra = _load_json(self.extra_json, {}) or {}
        for k, v in updates.items():
            if k in self._SCALARS or k == "id":
                continue
            extra[k] = v
        self.extra_json = _dump_json(extra) or "{}"


# --- Misc helpers ----------------------------------------------------------


def _iso(value: Any) -> str | None:
    """Coerce datetimes / dates to ISO strings; pass strings through."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


# Mapping of "collection name" (basename of legacy JSON file, sans ext) to
# the ORM class that backs it. Used by ``SQLStore``.
COLLECTION_TO_MODEL = {
    "users": UserRow,
    "todos": TodoRow,
    "folders": FolderRow,
    "notifications": NotificationRow,
    "attachments": AttachmentRow,
    "reminder_send_log": ReminderLogRow,
}
