"""SQLAlchemy engine, session factory, and ``init_db`` helper.

Single SQLite file at ``data/app.db`` for the running app; tests can
override via ``make_engine(":memory:")``.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(__file__), "data", "app.db"
)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def make_engine(url: str | None = None):
    """Build a SQLAlchemy engine.

    Defaults to the on-disk ``data/app.db`` file. Pass ``":memory:"`` (or a
    full ``sqlite:///path`` URL) to override. Enables ``check_same_thread``
    so the engine is usable from the scheduler task.
    """
    if url is None:
        os.makedirs(os.path.dirname(DEFAULT_DB_PATH), exist_ok=True)
        url = f"sqlite:///{DEFAULT_DB_PATH}"
    elif url == ":memory:":
        url = "sqlite:///:memory:"
    elif not url.startswith("sqlite:"):
        url = f"sqlite:///{url}"

    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, future=True, connect_args=connect_args)


def make_session_factory(engine):
    """Return a ``sessionmaker`` bound to ``engine``."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db(engine) -> None:
    """Create all tables. Idempotent — safe to call on every startup."""
    # Import here to avoid circular import at module load.
    from db_models import (  # noqa: F401  (registers models on Base)
        AttachmentRow,
        FolderRow,
        NotificationRow,
        ReminderLogRow,
        TodoRow,
        UserRow,
    )

    Base.metadata.create_all(engine)
