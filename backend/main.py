"""FastAPI application entry point."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from exceptions import (
    ConflictError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
    conflict_error_handler,
    not_found_error_handler,
    unauthorized_error_handler,
    validation_error_handler,
)
from routers.ai import router as ai_router
from routers.attachments import router as attachments_router
from routers.auth import router as auth_router
from routers.comments import router as comments_router
from routers.folders import router as folders_router
from routers.notifications import router as notifications_router
from routers.todos import router as todos_router
from routers.users import router as users_router

app = FastAPI(title="Todo App API", version="1.0.0")

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

# Register custom exception handlers
app.add_exception_handler(ValidationError, validation_error_handler)
app.add_exception_handler(ConflictError, conflict_error_handler)
app.add_exception_handler(UnauthorizedError, unauthorized_error_handler)
app.add_exception_handler(NotFoundError, not_found_error_handler)

# Include routers
app.include_router(auth_router)
app.include_router(todos_router)
app.include_router(comments_router)
app.include_router(attachments_router)
app.include_router(folders_router)
app.include_router(notifications_router)
app.include_router(ai_router)
app.include_router(users_router)

# Serve uploaded images
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "data", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Todo App API"}
