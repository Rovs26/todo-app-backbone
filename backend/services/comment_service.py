"""Comment service: nested threads with mentions and image attachments.

Comments live as a list on the parent ``Todo`` record. Atomicity is
achieved by writing the whole Todo back via ``JSONStore.update``.
"""

import uuid
from datetime import datetime, timezone

from exceptions import NotFoundError, ValidationError
from models import Attachment, Comment, CommentCreate, CommentResponse, CommentUpdate, MentionRef
from services.attachment_service import AttachmentService
from services.auth_service import AuthService
from services.mention_extractor import extract_mention_usernames
from store import JSONStore

MAX_THREAD_DEPTH = 5


class CommentService:
    def __init__(
        self,
        todo_store: JSONStore,
        user_store: JSONStore,
        auth_service: AuthService,
        attachment_service: AttachmentService,
    ):
        self.todo_store = todo_store
        self.user_store = user_store
        self.auth_service = auth_service
        self.attachment_service = attachment_service

    # --- Public API ---

    def list_comments(self, user_id: str, todo_id: str) -> list[CommentResponse]:
        todo = self._get_owned_todo(user_id, todo_id)
        return [self._to_response(c) for c in todo.get("comments") or []]

    def create_comment(
        self,
        user_id: str,
        todo_id: str,
        data: CommentCreate,
    ) -> CommentResponse:
        todo = self._get_owned_todo(user_id, todo_id)
        comments = list(todo.get("comments") or [])

        body = data.body
        if not body.strip():
            raise ValidationError(
                [{"field": "body", "message": "Body must not be blank"}]
            )

        parent_id = data.parent_comment_id
        if parent_id:
            parent = self._find_in(comments, parent_id)
            if not parent:
                raise NotFoundError("Parent comment not found")
            depth = self._depth_of(comments, parent_id) + 1
            if depth > MAX_THREAD_DEPTH:
                raise ValidationError(
                    [{"field": "parent_comment_id", "message": "Thread is too deep"}]
                )

        comment_id = str(uuid.uuid4())
        mentions = self._resolve_mentions(body)
        attachment_ids = list(data.attachment_ids or [])
        if attachment_ids:
            self.attachment_service.bind_to_comment(
                owner_id=user_id,
                attachment_ids=attachment_ids,
                comment_id=comment_id,
                todo_id=todo_id,
            )

        row = {
            "id": comment_id,
            "todo_id": todo_id,
            "author_id": user_id,
            "parent_comment_id": parent_id,
            "body": body,
            "attachment_ids": attachment_ids,
            "mentions": [m.model_dump() for m in mentions],
            "is_tombstone": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }
        comments.append(row)
        self.todo_store.update(todo_id, {"comments": comments})
        return self._to_response(row)

    def update_comment(
        self,
        user_id: str,
        todo_id: str,
        comment_id: str,
        data: CommentUpdate,
    ) -> CommentResponse:
        todo = self._get_owned_todo(user_id, todo_id)
        comments = list(todo.get("comments") or [])
        target = self._find_in(comments, comment_id)
        if not target or target.get("author_id") != user_id:
            raise NotFoundError("Comment not found")
        if target.get("is_tombstone"):
            raise NotFoundError("Comment not found")

        body = data.body
        if not body.strip():
            raise ValidationError(
                [{"field": "body", "message": "Body must not be blank"}]
            )

        new_ids = list(data.attachment_ids or [])
        # unbind removed attachments first, then rebind kept/new
        self.attachment_service.unbind_from_comment(
            comment_id=comment_id, keep_ids=new_ids
        )
        if new_ids:
            self.attachment_service.bind_to_comment(
                owner_id=user_id,
                attachment_ids=new_ids,
                comment_id=comment_id,
                todo_id=todo_id,
            )

        mentions = self._resolve_mentions(body)
        target["body"] = body
        target["attachment_ids"] = new_ids
        target["mentions"] = [m.model_dump() for m in mentions]
        target["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.todo_store.update(todo_id, {"comments": comments})
        return self._to_response(target)

    def delete_comment(
        self,
        user_id: str,
        todo_id: str,
        comment_id: str,
    ) -> None:
        todo = self._get_owned_todo(user_id, todo_id)
        comments = list(todo.get("comments") or [])
        target = self._find_in(comments, comment_id)
        if not target or target.get("author_id") != user_id:
            raise NotFoundError("Comment not found")

        has_children = any(
            c.get("parent_comment_id") == comment_id for c in comments
        )

        attachment_ids = list(target.get("attachment_ids") or [])

        if has_children:
            # tombstone in place
            target["is_tombstone"] = True
            target["body"] = ""
            target["attachment_ids"] = []
            target["mentions"] = []
            target["updated_at"] = datetime.now(timezone.utc).isoformat()
            new_comments = comments
        else:
            new_comments = [c for c in comments if c.get("id") != comment_id]

        # unbind + delete any attachments that lose their last reference
        if attachment_ids:
            self.attachment_service.unbind_from_comment(
                comment_id=comment_id, keep_ids=[]
            )
            self.attachment_service.delete_unreferenced(attachment_ids)

        self.todo_store.update(todo_id, {"comments": new_comments})

    # --- Helpers ---

    def _get_owned_todo(self, user_id: str, todo_id: str) -> dict:
        record = self.todo_store.find_by_id(todo_id)
        if not record or record.get("user_id") != user_id:
            raise NotFoundError("Todo not found")
        if "comments" not in record:
            record["comments"] = []
        return record

    @staticmethod
    def _find_in(comments: list[dict], comment_id: str) -> dict | None:
        for c in comments:
            if c.get("id") == comment_id:
                return c
        return None

    @classmethod
    def _depth_of(cls, comments: list[dict], comment_id: str) -> int:
        """1 = top-level. Cycle-safe via visited set."""
        by_id = {c["id"]: c for c in comments}
        depth = 1
        seen: set[str] = set()
        current = by_id.get(comment_id)
        while current and current.get("parent_comment_id"):
            cid = current["id"]
            if cid in seen:
                break
            seen.add(cid)
            depth += 1
            current = by_id.get(current["parent_comment_id"])
            if depth > MAX_THREAD_DEPTH + 5:  # hard stop
                break
        return depth

    def _resolve_mentions(self, body: str) -> list[MentionRef]:
        names = extract_mention_usernames(body)
        if not names:
            return []
        resolved: list[MentionRef] = []
        seen_ids: set[str] = set()
        for name in names:
            row = self.user_store.find_by_field("username", name)
            if not row:
                # case-insensitive fallback
                for r in self.user_store.read_all():
                    if str(r.get("username", "")).lower() == name.lower():
                        row = r
                        break
            if not row:
                continue
            uid = row["id"]
            if uid in seen_ids:
                continue
            seen_ids.add(uid)
            resolved.append(MentionRef(username=name, user_id=uid))
        return resolved

    def _to_response(self, row: dict) -> CommentResponse:
        author_username = ""
        author = self.user_store.find_by_id(row.get("author_id", ""))
        if author:
            author_username = author.get("username", "")

        attachments: list[Attachment] = []
        ids = row.get("attachment_ids") or []
        if ids:
            attachments = self.attachment_service.list_for_ids(ids)

        return CommentResponse(
            id=row["id"],
            todo_id=row["todo_id"],
            author_id=row["author_id"],
            author_username=author_username,
            parent_comment_id=row.get("parent_comment_id"),
            body=row.get("body", ""),
            attachments=attachments,
            mentions=[MentionRef(**m) for m in (row.get("mentions") or [])],
            is_tombstone=bool(row.get("is_tombstone")),
            created_at=row["created_at"],
            updated_at=row.get("updated_at"),
        )
