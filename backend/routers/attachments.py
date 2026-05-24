"""Attachment endpoints for comment image uploads."""

from fastapi import APIRouter, Depends, File, Response, UploadFile

from dependencies import get_current_user
from models import Attachment, User
from routers.comments import attachment_service

router = APIRouter(prefix="/api/comment-attachments", tags=["attachments"])


@router.post("", response_model=Attachment, status_code=201)
async def upload_attachment(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> Attachment:
    contents = await file.read()
    return attachment_service.upload(
        owner_id=current_user.id,
        contents=contents,
        mime_type=file.content_type or "application/octet-stream",
        original_name=file.filename,
    )


@router.delete("/{attachment_id}", status_code=204)
async def delete_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
) -> Response:
    attachment_service.delete_unbound_owned(current_user.id, attachment_id)
    return Response(status_code=204)
