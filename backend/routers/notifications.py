"""Notification API endpoints.

Detection runs synchronously on every list call so the user always sees
up-to-date data without needing a background scheduler.
"""

import os

from fastapi import APIRouter, Depends, Query, Response

from dependencies import get_current_user, session_factory
from models import User
from routers.todos import todo_store
from services.notification_service import NotificationService
from store import SQLStore

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
notification_store = SQLStore(session_factory, os.path.join(DATA_DIR, "notifications.json"))
notification_service = NotificationService(notification_store, todo_store)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    unread_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """List the user's notifications (newest first).

    Detection runs first so any newly-due reminders are persisted before the
    list is returned.
    """
    notification_service.detect_for_user(current_user.id)
    return notification_service.list_for_user(current_user.id, unread_only=unread_only)


@router.post("/check")
async def check_now(
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Force a detection pass and return only the freshly created notifications."""
    return notification_service.detect_for_user(current_user.id)


@router.get("/unread-count")
async def unread_count(
    current_user: User = Depends(get_current_user),
) -> dict:
    notification_service.detect_for_user(current_user.id)
    return {"count": notification_service.unread_count(current_user.id)}


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    return notification_service.mark_read(current_user.id, notification_id)


@router.post("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
) -> dict:
    count = notification_service.mark_all_read(current_user.id)
    return {"updated": count}


@router.delete("", status_code=200)
async def clear_all(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Remove every notification for the user."""
    count = notification_service.clear_all(current_user.id)
    return {"removed": count}
