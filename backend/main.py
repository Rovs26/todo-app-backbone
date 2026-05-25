"""FastAPI application entry point."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

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
from services.email_service import build_email_service
from services.reminder_scheduler import ReminderScheduler
from store import JSONStore

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: build email service + scheduler
    email_service = build_email_service(
        os.environ, default_log_path=os.path.join(DATA_DIR, "email_log.jsonl")
    )
    todo_store = JSONStore(os.path.join(DATA_DIR, "todos.json"))
    user_store = JSONStore(os.path.join(DATA_DIR, "users.json"))
    log_store = JSONStore(os.path.join(DATA_DIR, "reminder_send_log.json"))
    rate_cap = int(os.environ.get("REMINDER_RATE_LIMIT_PER_MINUTE", "100"))
    scheduler = ReminderScheduler(
        todo_store=todo_store,
        user_store=user_store,
        email_service=email_service,
        log_store=log_store,
        rate_limit_per_minute=rate_cap,
    )
    app.state.reminder_scheduler = scheduler
    app.state.reminder_task = asyncio.create_task(scheduler.run())
    log.info("ReminderScheduler started (rate_cap=%d/min)", rate_cap)
    try:
        yield
    finally:
        # Shutdown: stop scheduler and await within 5s
        try:
            await asyncio.wait_for(scheduler.stop(), timeout=5.0)
            await asyncio.wait_for(app.state.reminder_task, timeout=5.0)
        except (asyncio.TimeoutError, Exception):
            log.warning("ReminderScheduler shutdown timed out")

app = FastAPI(title="Todo App API", version="1.0.0", lifespan=lifespan)

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
