"""Comment endpoints nested under /api/todos/{todo_id}/comments."""

import os

from fastapi import APIRouter, Depends, Response

from dependencies import get_current_user, user_store
from models import CommentCreate, CommentResponse, CommentUpdate, User
from services.attachment_service import AttachmentService
from services.auth_service import AuthService
from services.comment_service import CommentService
from store import JSONStore

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
todo_store = JSONStore(os.path.join(DATA_DIR, "todos.json"))
attachment_store = JSONStore(os.path.join(DATA_DIR, "attachments.json"))
attachment_uploads_dir = os.path.join(DATA_DIR, "uploads", "comments")
attachment_service = AttachmentService(attachment_store, attachment_uploads_dir)
auth_service = AuthService(user_store)
comment_service = CommentService(
    todo_store=todo_store,
    user_store=user_store,
    auth_service=auth_service,
    attachment_service=attachment_service,
)

router = APIRouter(prefix="/api/todos", tags=["comments"])


@router.get("/{todo_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    todo_id: str,
    current_user: User = Depends(get_current_user),
) -> list[CommentResponse]:
    return comment_service.list_comments(current_user.id, todo_id)


@router.post("/{todo_id}/comments", response_model=CommentResponse, status_code=201)
async def create_comment(
    todo_id: str,
    data: CommentCreate,
    current_user: User = Depends(get_current_user),
) -> CommentResponse:
    return comment_service.create_comment(current_user.id, todo_id, data)


@router.put(
    "/{todo_id}/comments/{comment_id}",
    response_model=CommentResponse,
)
async def update_comment(
    todo_id: str,
    comment_id: str,
    data: CommentUpdate,
    current_user: User = Depends(get_current_user),
) -> CommentResponse:
    return comment_service.update_comment(current_user.id, todo_id, comment_id, data)


@router.delete("/{todo_id}/comments/{comment_id}", status_code=204)
async def delete_comment(
    todo_id: str,
    comment_id: str,
    current_user: User = Depends(get_current_user),
) -> Response:
    comment_service.delete_comment(current_user.id, todo_id, comment_id)
    return Response(status_code=204)
