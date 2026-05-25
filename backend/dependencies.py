"""FastAPI dependencies for request processing.

Owns the shared SQLAlchemy engine + session factory used by every
SQLStore-backed router. Tests don't import this module, so the engine
is only created when the live app boots.
"""

import os

from fastapi import Request

from db import init_db, make_engine, make_session_factory
from exceptions import UnauthorizedError
from models import User
from services.auth_service import AuthService
from store import SQLStore

# DB engine + session factory — shared across the whole running app.
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
engine = make_engine()
session_factory = make_session_factory(engine)
# Ensure schema exists before any router creates a store.
init_db(engine)

# Initialize user store and auth service.
user_store = SQLStore(session_factory, os.path.join(DATA_DIR, "users.json"))
auth_service = AuthService(user_store)


async def get_current_user(request: Request) -> User:
    """Extract and validate JWT from httpOnly cookie, return User.

    Extracts the JWT token from the 'token' httpOnly cookie,
    verifies the token signature and expiry, loads the user from
    the store, and returns the User object.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The authenticated User object.

    Raises:
        UnauthorizedError: If no token cookie is present, token is invalid,
            or the user referenced by the token does not exist.
    """
    token = request.cookies.get("token")
    if not token:
        raise UnauthorizedError("Authentication required")

    # verify_token raises UnauthorizedError if token is invalid/expired
    user_id = auth_service.verify_token(token)

    # Load user from store
    user = auth_service.get_user_by_id(user_id)
    if not user:
        raise UnauthorizedError("Authentication failed")

    return user
