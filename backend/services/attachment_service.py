"""Attachment service for comment image uploads.

Persistence model:
- Registry: ``data/attachments.json`` (one row per uploaded file).
- Files: ``data/uploads/comments/<uuid>.<ext>``.
- Lifecycle:
  - ``upload`` writes the file and adds an unbound registry row.
  - ``bind_to_comment`` sets ``comment_id`` and ``todo_id`` on the row.
  - ``unbind_from_comment`` clears them (used on comment edit when an
    attachment is removed from the list).
  - ``delete_unreferenced`` removes any row whose ``id`` is not in the
    provided id set, deleting the underlying file too.
  - ``sweep_orphans`` removes unbound rows older than ``max_age_seconds``.
"""

import os
import re
import uuid
from datetime import datetime, timedelta, timezone

from exceptions import NotFoundError, ValidationError
from models import Attachment
from store import JSONStore

ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB

_EXT_BY_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename(name: str | None) -> str:
    if not name:
        return "upload"
    base = os.path.basename(name)
    base = _SAFE_NAME_RE.sub("_", base).strip("._-") or "upload"
    return base[:120]


class AttachmentService:
    def __init__(self, store: JSONStore, uploads_dir: str):
        self.store = store
        self.uploads_dir = uploads_dir
        os.makedirs(self.uploads_dir, exist_ok=True)

    # --- Upload / lookup ---

    def upload(
        self,
        owner_id: str,
        contents: bytes,
        mime_type: str,
        original_name: str | None,
    ) -> Attachment:
        if mime_type not in ALLOWED_MIME_TYPES:
            raise ValidationError(
                [{"field": "file", "message": f"Unsupported MIME type: {mime_type}"}]
            )
        if len(contents) > MAX_BYTES:
            raise ValidationError(
                [{"field": "file", "message": f"File exceeds {MAX_BYTES} bytes"}]
            )

        ext = _EXT_BY_MIME[mime_type]
        attachment_id = str(uuid.uuid4())
        on_disk_name = f"{attachment_id}{ext}"
        full_path = os.path.join(self.uploads_dir, on_disk_name)
        with open(full_path, "wb") as fh:
            fh.write(contents)

        row = {
            "id": attachment_id,
            "owner_id": owner_id,
            "comment_id": None,
            "todo_id": None,
            "url": f"/uploads/comments/{on_disk_name}",
            "mime_type": mime_type,
            "size_bytes": len(contents),
            "original_name": _sanitize_filename(original_name),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.store.add(row)
        return Attachment(**row)

    def get(self, attachment_id: str) -> Attachment | None:
        row = self.store.find_by_id(attachment_id)
        return Attachment(**row) if row else None

    def list_for_ids(self, ids: list[str]) -> list[Attachment]:
        if not ids:
            return []
        keep = set(ids)
        return [
            Attachment(**r) for r in self.store.read_all() if r.get("id") in keep
        ]

    # --- Ownership-checked bind / unbind ---

    def bind_to_comment(
        self,
        owner_id: str,
        attachment_ids: list[str],
        comment_id: str,
        todo_id: str,
    ) -> list[Attachment]:
        """Bind every id to (comment_id, todo_id). Atomic in one write.

        Each id must belong to ``owner_id`` and must be either unbound or
        already bound to the same comment_id (idempotent on edit).
        """
        if not attachment_ids:
            return []
        rows = self.store.read_all()
        by_id = {r["id"]: r for r in rows}
        for aid in attachment_ids:
            row = by_id.get(aid)
            if not row:
                raise ValidationError(
                    [{"field": "attachment_ids", "message": f"Unknown attachment: {aid}"}]
                )
            if row.get("owner_id") != owner_id:
                raise NotFoundError("Attachment not found")
            bound = row.get("comment_id")
            if bound and bound != comment_id:
                raise ValidationError(
                    [{"field": "attachment_ids", "message": f"Attachment already bound: {aid}"}]
                )
        for aid in attachment_ids:
            by_id[aid]["comment_id"] = comment_id
            by_id[aid]["todo_id"] = todo_id
        self.store.write_all(rows)
        return [Attachment(**by_id[aid]) for aid in attachment_ids]

    def unbind_from_comment(self, comment_id: str, keep_ids: list[str]) -> None:
        """Unbind any attachment previously bound to comment_id that is not
        in keep_ids. Files are NOT deleted here — call delete_unreferenced
        afterwards to garbage-collect those that are also not referenced
        elsewhere.
        """
        rows = self.store.read_all()
        keep = set(keep_ids)
        for r in rows:
            if r.get("comment_id") == comment_id and r.get("id") not in keep:
                r["comment_id"] = None
                r["todo_id"] = None
        self.store.write_all(rows)

    def delete_unreferenced(self, candidate_ids: list[str]) -> int:
        """Delete each candidate that is currently unbound. Returns count deleted."""
        if not candidate_ids:
            return 0
        rows = self.store.read_all()
        keep_set = set(candidate_ids)
        removed = 0
        survivors: list[dict] = []
        for r in rows:
            if r.get("id") in keep_set and not r.get("comment_id"):
                self._delete_file_for_row(r)
                removed += 1
                continue
            survivors.append(r)
        if removed:
            self.store.write_all(survivors)
        return removed

    # --- DELETE endpoint helper ---

    def delete_unbound_owned(self, owner_id: str, attachment_id: str) -> None:
        rows = self.store.read_all()
        for r in rows:
            if r.get("id") == attachment_id:
                if r.get("owner_id") != owner_id:
                    raise NotFoundError("Attachment not found")
                if r.get("comment_id"):
                    raise ValidationError(
                        [{"field": "attachment_id", "message": "Attachment is bound"}]
                    )
                self._delete_file_for_row(r)
                new_rows = [x for x in rows if x.get("id") != attachment_id]
                self.store.write_all(new_rows)
                return
        raise NotFoundError("Attachment not found")

    # --- Maintenance ---

    def sweep_orphans(self, max_age_seconds: int = 3600) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
        rows = self.store.read_all()
        survivors: list[dict] = []
        removed = 0
        for r in rows:
            if r.get("comment_id"):
                survivors.append(r)
                continue
            try:
                created = datetime.fromisoformat(str(r.get("created_at")))
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
            except ValueError:
                survivors.append(r)
                continue
            if created < cutoff:
                self._delete_file_for_row(r)
                removed += 1
            else:
                survivors.append(r)
        if removed:
            self.store.write_all(survivors)
        return removed

    # --- internals ---

    def _delete_file_for_row(self, row: dict) -> None:
        url = row.get("url") or ""
        if not url.startswith("/uploads/comments/"):
            return
        name = os.path.basename(url)
        path = os.path.join(self.uploads_dir, name)
        if os.path.exists(path):
            try:
                os.unlink(path)
            except OSError:
                pass
