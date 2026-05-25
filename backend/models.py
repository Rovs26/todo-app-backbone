"""Pydantic data models for the Todo application."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


# --- User Models ---


class User(BaseModel):
    """Internal user model with all fields including password hash."""

    id: str  # UUID4 string
    email: EmailStr  # Valid email format
    username: str  # 3-30 chars, alphanumeric + underscore
    password_hash: str  # bcrypt hash
    created_at: datetime  # ISO 8601 timestamp
    email_reminders_enabled: bool = True  # User opt-out for reminder emails


class UserCreate(BaseModel):
    """Request model for user registration."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=8)
    password_confirm: str


class UserResponse(BaseModel):
    """Response model for user data (excludes password_hash)."""

    id: str
    email: str
    username: str
    created_at: datetime
    email_reminders_enabled: bool = True


class UserPreferencesUpdate(BaseModel):
    """Request body for updating user preferences via PUT /api/auth/me."""

    email_reminders_enabled: bool


# --- Enums ---


class Priority(str, Enum):
    """Priority levels for todo items."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Status(str, Enum):
    """Status values for todo items."""

    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    DONE = "done"


class Recurrence(str, Enum):
    """Recurrence cadence for todos."""

    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


# --- Todo Models ---


class Subtask(BaseModel):
    """A single sub-item on a todo (used for checklists)."""

    id: str
    title: str = Field(min_length=1, max_length=200)
    done: bool = False


class Todo(BaseModel):
    """Internal todo model with all fields."""

    id: str  # UUID4 string
    user_id: str  # Reference to User.id
    title: str  # 1-200 chars, non-whitespace-only
    description: str | None = None  # Optional, max 2000 chars
    priority: Priority = Priority.MEDIUM
    due_date: str | None = None  # ISO 8601 date (YYYY-MM-DD) or None
    reminder_at: datetime | None = None  # ISO 8601 datetime for reminder trigger
    reminder_sent: bool = False  # True once dispatched (or skipped)
    reminder_sent_at: datetime | None = None  # When the email was dispatched / skipped
    status: Status = Status.PENDING
    folder_id: str | None = None  # Optional grouping under a Folder
    tags: list[str] = Field(default_factory=list)  # User-defined labels
    subtasks: list[Subtask] = Field(default_factory=list)
    image_url: str | None = None  # Server-relative URL (set by upload endpoint)
    position: int = 0  # User-defined ordering (lower first)
    time_spent_seconds: int = 0  # Pomodoro / focus time accumulator
    comments: list["Comment"] = Field(default_factory=list)
    recurrence: Recurrence = Recurrence.NONE
    recurrence_until: str | None = None  # ISO 8601 date or None
    recurrence_count: int | None = None  # positive int or None
    recurrence_series_id: str | None = None  # shared UUID across occurrences
    recurrence_index: int = 0  # 0-based position in series
    created_at: datetime
    updated_at: datetime | None = None


# --- Comment / Attachment / Mention Models ---


class Attachment(BaseModel):
    """An image attachment uploaded by a user.

    Registered in ``data/attachments.json`` at upload time. The file is
    bound to a Comment when the comment is created or edited.
    """

    id: str  # UUID4 string
    owner_id: str  # User.id who uploaded it
    comment_id: str | None = None  # null until bound to a comment
    todo_id: str | None = None  # mirrors the comment's todo when bound
    url: str  # Server-relative URL, e.g. /uploads/comments/<uuid>.png
    mime_type: str  # png|jpeg|gif|webp
    size_bytes: int
    original_name: str  # sanitized; never used for the on-disk filename
    created_at: datetime


class MentionRef(BaseModel):
    """A resolved @mention pair inside a comment body."""

    username: str  # Original token text (case preserved)
    user_id: str  # Resolved User.id


class Comment(BaseModel):
    """Internal comment model (persisted as element of ``Todo.comments``)."""

    id: str
    todo_id: str
    author_id: str
    parent_comment_id: str | None = None  # null = top-level
    body: str
    attachment_ids: list[str] = Field(default_factory=list)
    mentions: list[MentionRef] = Field(default_factory=list)
    is_tombstone: bool = False
    created_at: datetime
    updated_at: datetime | None = None


class CommentResponse(BaseModel):
    """Read-shape comment for API responses (denormalized helpers)."""

    id: str
    todo_id: str
    author_id: str
    author_username: str
    parent_comment_id: str | None = None
    body: str
    attachments: list[Attachment] = Field(default_factory=list)
    mentions: list[MentionRef] = Field(default_factory=list)
    is_tombstone: bool = False
    created_at: datetime
    updated_at: datetime | None = None


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    parent_comment_id: str | None = None
    attachment_ids: list[str] = Field(default_factory=list, max_length=4)


class CommentUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    attachment_ids: list[str] = Field(default_factory=list, max_length=4)


# Forward-ref resolution for Todo.comments
Todo.model_rebuild()


class TodoCreate(BaseModel):
    """Request model for creating a todo."""

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    priority: Priority = Priority.MEDIUM
    due_date: str | None = None  # Validated as YYYY-MM-DD
    reminder_at: str | None = None  # ISO 8601 datetime string
    status: Status = Status.PENDING
    folder_id: str | None = None
    tags: list[str] | None = None
    subtasks: list[Subtask] | None = None
    recurrence: Recurrence | None = None
    recurrence_until: str | None = None
    recurrence_count: int | None = None


class TodoUpdate(BaseModel):
    """Request model for updating a todo (all fields optional)."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    priority: Priority | None = None
    due_date: str | None = None
    reminder_at: str | None = None  # ISO 8601 datetime string, explicit null clears
    status: Status | None = None
    folder_id: str | None = None  # Empty string clears the folder assignment
    tags: list[str] | None = None
    subtasks: list[Subtask] | None = None
    position: int | None = None
    recurrence: Recurrence | None = None
    recurrence_until: str | None = None
    recurrence_count: int | None = None


class TodoStats(BaseModel):
    """Statistics model for dashboard display."""

    total: int
    completed: int
    pending: int
    overdue: int


class StreakStats(BaseModel):
    """Completion-streak statistics for the dashboard."""

    today_completed: int
    week_completed: int
    current_streak_days: int
    longest_streak_days: int
    last_completion_date: str | None = None


# --- Folder Models ---


class Folder(BaseModel):
    """A folder / category that groups related todos for one user."""

    id: str
    user_id: str
    name: str = Field(min_length=1, max_length=80)
    color: str | None = None  # Free-form hex like #6366F1
    icon: str | None = None  # Optional emoji or short label
    created_at: datetime
    updated_at: datetime | None = None


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str | None = None
    icon: str | None = None


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = None
    icon: str | None = None
