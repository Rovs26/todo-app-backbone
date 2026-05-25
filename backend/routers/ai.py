"""AI endpoints: Whisper transcription and the conversational assistant."""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from dependencies import get_current_user
from models import User
from routers.comments import comment_service
from routers.folders import folder_service
from routers.todos import todo_service
from services import ai_service, voice_agent

router = APIRouter(prefix="/api/ai", tags=["ai"])


MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB — Whisper's per-file ceiling
ALLOWED_AUDIO_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
}


@router.get("/status")
async def status() -> dict:
    return {"enabled": ai_service.is_enabled()}


@router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Transcribe a short audio recording with Whisper.

    Returns ``{"text": str | None, "source": "whisper"|"unavailable"}``. The
    frontend uses this when present; falling back to Web Speech locally.
    """
    if not ai_service.is_enabled():
        return {"text": None, "source": "unavailable"}

    content_type = (file.content_type or "").lower()
    # Some browsers send "audio/webm; codecs=opus" — strip params before checking.
    short_type = content_type.split(";")[0].strip()
    if short_type and short_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported audio type: {short_type}")

    audio = await file.read()
    if len(audio) == 0:
        raise HTTPException(status_code=400, detail="Empty audio upload")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio too large (max 25 MB)")

    text = ai_service.transcribe_audio(audio, file.filename or "audio.webm")
    return {"text": text, "source": "whisper" if text else "unavailable"}


class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list)
    # Optional client-supplied weather snapshot (current + 3-day forecast from
    # Open-Meteo via the frontend `useWeather` composable). Free-form dict so
    # we don't have to re-validate the Open-Meteo schema on the server.
    weather: dict | None = None


class ChatResponse(BaseModel):
    reply: str
    source: str


OCR_UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "uploads", "ocr"
)
os.makedirs(OCR_UPLOAD_DIR, exist_ok=True)

ALLOWED_OCR_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}
MAX_OCR_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB
_OCR_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


@router.post("/parse-image")
async def parse_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Extract a list of todo candidates from an uploaded image.

    Saves the upload under ``data/uploads/ocr/<uuid>.<ext>`` and returns
    ``{items, image_url}``. The frontend renders ``items`` as a checklist
    that the user reviews before creating individual todos.
    """
    if not ai_service.is_enabled():
        raise HTTPException(
            status_code=503,
            detail="Vision OCR requires an OpenAI API key. Set OPENAI_API_KEY to enable.",
        )

    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if content_type not in ALLOWED_OCR_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported image type: {content_type}")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty image upload")
    if len(contents) > MAX_OCR_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 8 MB)")

    ext = _OCR_EXT[content_type]
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(OCR_UPLOAD_DIR, filename)
    with open(path, "wb") as fh:
        fh.write(contents)
    image_url = f"/uploads/ocr/{filename}"

    try:
        result = ai_service.parse_image(contents, content_type)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Vision parser failed: {exc}",
        )

    return {"items": result.get("items", []), "image_url": image_url}


class VoiceActionContext(BaseModel):
    active_folder_id: str | None = None
    active_todo_id: str | None = None


class VoiceActionRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=2000)
    context: VoiceActionContext | None = None


class VoiceApplyRequest(BaseModel):
    actions: list[dict] = Field(default_factory=list)


@router.post("/voice-action")
async def plan_voice_action(
    body: VoiceActionRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Plan a list of structured actions from a spoken transcript.

    Pure plan — no mutations. The frontend shows the proposal to the user
    for confirmation before the apply endpoint is called.
    """
    if not ai_service.is_enabled():
        raise HTTPException(
            status_code=503,
            detail="Voice agent requires an OpenAI API key.",
        )

    folders = [f.model_dump() for f in folder_service.list_for_user(current_user.id)]
    todos = [t.model_dump(mode="json") for t in todo_service.list_todos(user_id=current_user.id)]
    todos.sort(
        key=lambda t: (t.get("updated_at") or t.get("created_at") or ""),
        reverse=True,
    )

    try:
        result = voice_agent.plan(
            transcript=body.transcript, folders=folders, todos=todos
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Voice planner failed: {exc}")
    return result


@router.post("/voice-action/apply")
async def apply_voice_action(
    body: VoiceApplyRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Execute the user-approved actions in order."""
    return voice_agent.apply(
        user_id=current_user.id,
        actions=body.actions,
        folder_service=folder_service,
        todo_service=todo_service,
        comment_service=comment_service,
    )


class ParseTodoRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


@router.post("/parse-todo")
async def parse_todo(
    body: ParseTodoRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Parse a natural-language phrase into structured todo fields.

    Returns ``{"data": {...}, "source": "openai"|"local", "error"?: str}``.
    Never auto-creates a todo — the frontend opens the create modal with the
    parsed fields pre-filled so the user can review/edit/confirm.
    """
    folders = [
        f.model_dump() for f in folder_service.list_for_user(current_user.id)
    ]
    return ai_service.parse_todo(text=body.text, folders=folders)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    """Reply to ``body.message`` using the user's todos as grounding context."""
    if not ai_service.is_enabled():
        return ChatResponse(
            reply=(
                "AI assistant is not configured. Set OPENAI_API_KEY in "
                ".env.local to enable this."
            ),
            source="unavailable",
        )

    todos = [t.model_dump() for t in todo_service.list_todos(user_id=current_user.id)]
    folders = [
        f.model_dump() for f in folder_service.list_for_user(current_user.id)
    ]

    reply = ai_service.chat(
        user_message=body.message,
        history=[h.model_dump() for h in body.history],
        todos=todos,
        folders=folders,
        weather=body.weather,
    )

    if not reply:
        return ChatResponse(
            reply="I couldn't generate a reply just now. Try again in a moment.",
            source="error",
        )
    return ChatResponse(reply=reply, source="openai")
