"""Folders / categories router."""

import os

from fastapi import APIRouter, Depends, Query, Response

from dependencies import get_current_user, session_factory
from models import Folder, FolderCreate, FolderUpdate, User
from routers.todos import todo_store
from services.folder_service import FolderService
from store import SQLStore

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
folder_store = SQLStore(session_factory, os.path.join(DATA_DIR, "folders.json"))
folder_service = FolderService(folder_store, todo_store)

router = APIRouter(prefix="/api/folders", tags=["folders"])


@router.get("", response_model=list[Folder])
async def list_folders(current_user: User = Depends(get_current_user)) -> list[Folder]:
    return folder_service.list_for_user(current_user.id)


@router.get("/stats")
async def folder_stats(current_user: User = Depends(get_current_user)) -> list[dict]:
    return folder_service.folder_stats(current_user.id)


@router.post("", response_model=Folder, status_code=201)
async def create_folder(
    data: FolderCreate,
    current_user: User = Depends(get_current_user),
) -> Folder:
    return folder_service.create(current_user.id, data)


@router.get("/{folder_id}", response_model=Folder)
async def get_folder(
    folder_id: str,
    current_user: User = Depends(get_current_user),
) -> Folder:
    return folder_service.get(current_user.id, folder_id)


@router.put("/{folder_id}", response_model=Folder)
async def update_folder(
    folder_id: str,
    data: FolderUpdate,
    current_user: User = Depends(get_current_user),
) -> Folder:
    return folder_service.update(current_user.id, folder_id, data)


@router.delete("/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: str,
    current_user: User = Depends(get_current_user),
) -> Response:
    folder_service.delete(current_user.id, folder_id)
    return Response(status_code=204)
