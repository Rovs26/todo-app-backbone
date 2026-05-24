"""User-search endpoint used by @mention autocomplete in comments."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from dependencies import get_current_user, user_store
from exceptions import ValidationError
from models import User


class UserSearchResult(BaseModel):
    id: str
    username: str


router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/search", response_model=list[UserSearchResult])
async def search_users(
    q: str = Query(default="", description="Username prefix"),
    current_user: User = Depends(get_current_user),
) -> list[UserSearchResult]:
    q_clean = (q or "").strip().lower()
    if not q_clean:
        raise ValidationError([{"field": "q", "message": "Query must not be empty"}])
    rows = user_store.read_all()
    matches: list[UserSearchResult] = []
    for r in rows:
        username = str(r.get("username", ""))
        if username.lower().startswith(q_clean):
            matches.append(UserSearchResult(id=r["id"], username=username))
            if len(matches) >= 8:
                break
    return matches
