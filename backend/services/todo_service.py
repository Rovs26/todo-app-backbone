"""Todo service handling CRUD operations scoped to authenticated users."""

import re
import uuid
from datetime import date, datetime, timezone

from exceptions import NotFoundError, ValidationError
from models import (
    Priority,
    Recurrence,
    Status,
    Subtask,
    Todo,
    TodoCreate,
    TodoStats,
    TodoUpdate,
)
from services.recurrence import next_occurrence_date, shift_reminder
from store import JSONStore


def _normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    seen: list[str] = []
    for raw in tags:
        if not isinstance(raw, str):
            continue
        cleaned = raw.strip().lower()
        if not cleaned:
            continue
        if len(cleaned) > 32:
            cleaned = cleaned[:32]
        if cleaned not in seen:
            seen.append(cleaned)
    return seen


def _normalize_subtasks(subtasks: list[Subtask] | list[dict] | None) -> list[dict]:
    if not subtasks:
        return []
    out: list[dict] = []
    for entry in subtasks:
        if isinstance(entry, Subtask):
            out.append(entry.model_dump())
            continue
        if not isinstance(entry, dict):
            continue
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        out.append(
            {
                "id": entry.get("id") or str(uuid.uuid4()),
                "title": title[:200],
                "done": bool(entry.get("done", False)),
            }
        )
    return out


class TodoService:
    """Handles CRUD operations on todos scoped to the authenticated user."""

    def __init__(self, todo_store: JSONStore):
        """Initialize with todo store.

        Args:
            todo_store: JSONStore instance for todo persistence.
        """
        self.todo_store = todo_store

    def create(self, user_id: str, data: TodoCreate) -> Todo:
        """Create a todo for the user.

        Validates title, sets defaults (priority=medium, status=pending),
        generates UUID, sets created_at, and persists to store.

        Args:
            user_id: The authenticated user's ID.
            data: TodoCreate model with todo fields.

        Returns:
            The created Todo object.

        Raises:
            ValidationError: If title is invalid or due_date format is wrong.
        """
        # Validate title is not whitespace-only
        if not data.title or not data.title.strip():
            raise ValidationError([{"field": "title", "message": "Title must not be blank"}])

        # Validate due_date format if provided
        if data.due_date is not None:
            self._validate_due_date(data.due_date)

        # Validate reminder_at format if provided
        reminder_at_value = None
        if data.reminder_at is not None:
            parsed_reminder = self._validate_reminder_at(data.reminder_at)
            reminder_at_value = parsed_reminder.isoformat()

        # Recurrence validation + series setup
        recurrence_value = (
            data.recurrence.value if data.recurrence else Recurrence.NONE.value
        )
        recurrence_until = data.recurrence_until
        recurrence_count = data.recurrence_count
        recurrence_series_id: str | None = None

        if recurrence_value != Recurrence.NONE.value:
            if not data.due_date:
                raise ValidationError(
                    [{"field": "due_date", "message": "Recurring todos require a due_date"}]
                )
            self._validate_recurrence_bounds(recurrence_until, recurrence_count, data.due_date)
            recurrence_series_id = str(uuid.uuid4())
        else:
            recurrence_until = None
            recurrence_count = None

        # Create todo record with defaults
        existing_records = self.todo_store.read_all()
        max_position = max(
            (r.get("position", 0) for r in existing_records if r.get("user_id") == user_id),
            default=-1,
        )
        todo_data = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "title": data.title,
            "description": data.description,
            "priority": data.priority.value if data.priority else Priority.MEDIUM.value,
            "due_date": data.due_date,
            "reminder_at": reminder_at_value,
            "status": data.status.value if data.status else Status.PENDING.value,
            "folder_id": data.folder_id,
            "tags": _normalize_tags(data.tags),
            "subtasks": _normalize_subtasks(data.subtasks),
            "image_url": None,
            "position": max_position + 1,
            "time_spent_seconds": 0,
            "comments": [],
            "recurrence": recurrence_value,
            "recurrence_until": recurrence_until,
            "recurrence_count": recurrence_count,
            "recurrence_series_id": recurrence_series_id,
            "recurrence_index": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }

        # If created already-done with recurrence, spawn next atomically.
        if (
            recurrence_value != Recurrence.NONE.value
            and todo_data["status"] == Status.DONE.value
        ):
            next_row = self._build_next_occurrence(todo_data)
            records = self.todo_store.read_all()
            records.append(todo_data)
            if next_row:
                records.append(next_row)
            self.todo_store.write_all(records)
        else:
            self.todo_store.add(todo_data)

        return Todo(**todo_data)

    def list_todos(
        self,
        user_id: str,
        status: str | None = None,
        priority: str | None = None,
        sort_by: str | None = None,
        tag: str | None = None,
        search: str | None = None,
        folder_id: str | None = None,
        recurrence: str | None = None,
    ) -> list[Todo]:
        """List user's todos with optional filtering and sorting.

        Filters by user_id, applies optional status/priority/tag/search/folder
        filters, and applies sort (due_date asc with nulls last, created_at
        desc, or manual ``position`` order).
        """
        # Validate filter values
        if status is not None:
            valid_statuses = [s.value for s in Status]
            if status not in valid_statuses:
                raise ValidationError(
                    [{"field": "status", "message": f"Invalid status value. Must be one of: {', '.join(valid_statuses)}"}]
                )

        if priority is not None:
            valid_priorities = [p.value for p in Priority]
            if priority not in valid_priorities:
                raise ValidationError(
                    [{"field": "priority", "message": f"Invalid priority value. Must be one of: {', '.join(valid_priorities)}"}]
                )

        if sort_by is not None:
            valid_sorts = ["due_date", "created_at", "position"]
            if sort_by not in valid_sorts:
                raise ValidationError(
                    [{"field": "sort_by", "message": f"Invalid sort_by value. Must be one of: {', '.join(valid_sorts)}"}]
                )

        if recurrence is not None:
            valid_rec = [r.value for r in Recurrence]
            if recurrence not in valid_rec:
                raise ValidationError(
                    [{"field": "recurrence", "message": f"Invalid recurrence. Must be one of: {', '.join(valid_rec)}"}]
                )

        # Get all records and filter by user_id
        all_records = self.todo_store.read_all()
        user_todos = [r for r in all_records if r.get("user_id") == user_id]

        # Apply status filter
        if status is not None:
            user_todos = [r for r in user_todos if r.get("status") == status]

        # Apply priority filter
        if priority is not None:
            user_todos = [r for r in user_todos if r.get("priority") == priority]

        # Apply tag filter (case-insensitive exact match)
        if tag is not None:
            tag_lower = tag.strip().lower()
            if tag_lower:
                user_todos = [r for r in user_todos if tag_lower in (r.get("tags") or [])]

        # Apply recurrence filter
        if recurrence is not None:
            user_todos = [r for r in user_todos if (r.get("recurrence") or "none") == recurrence]

        # Apply folder filter ("none" matches todos with no folder)
        if folder_id is not None:
            if folder_id == "none":
                user_todos = [r for r in user_todos if not r.get("folder_id")]
            else:
                user_todos = [r for r in user_todos if r.get("folder_id") == folder_id]

        # Apply free-text search across title + description + tags
        if search is not None:
            needle = search.strip().lower()
            if needle:
                def _matches(record: dict) -> bool:
                    title = (record.get("title") or "").lower()
                    description = (record.get("description") or "").lower()
                    tags = " ".join(record.get("tags") or []).lower()
                    return needle in title or needle in description or needle in tags

                user_todos = [r for r in user_todos if _matches(r)]

        # Apply sorting
        if sort_by == "due_date":
            user_todos.sort(key=lambda r: (r.get("due_date") is None, r.get("due_date") or ""))
        elif sort_by == "created_at":
            user_todos.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        elif sort_by == "position":
            user_todos.sort(key=lambda r: (r.get("position", 0), r.get("created_at", "")))

        return [Todo(**r) for r in user_todos]

    def get_by_id(self, user_id: str, todo_id: str) -> Todo:
        """Get a specific todo by ID.

        Finds the todo and verifies ownership. Returns 404 if not found or not owned.

        Args:
            user_id: The authenticated user's ID.
            todo_id: The todo's ID to retrieve.

        Returns:
            The Todo object.

        Raises:
            NotFoundError: If todo is not found or not owned by user.
        """
        record = self.todo_store.find_by_id(todo_id)

        if not record or record.get("user_id") != user_id:
            raise NotFoundError("Todo not found")

        return Todo(**record)

    def update(
        self,
        user_id: str,
        todo_id: str,
        data: TodoUpdate,
        apply_to: str = "occurrence",
    ) -> Todo:
        """Update a todo. ``apply_to=series`` cascades to future occurrences."""
        if apply_to not in ("occurrence", "series"):
            raise ValidationError(
                [{"field": "apply_to", "message": "apply_to must be 'occurrence' or 'series'"}]
            )

        record = self.todo_store.find_by_id(todo_id)
        if not record or record.get("user_id") != user_id:
            raise NotFoundError("Todo not found")

        updates: dict = {}

        if data.title is not None:
            if not data.title.strip():
                raise ValidationError([{"field": "title", "message": "Title must not be blank"}])
            updates["title"] = data.title

        if data.description is not None:
            updates["description"] = data.description

        if data.priority is not None:
            updates["priority"] = data.priority.value

        if data.due_date is not None:
            self._validate_due_date(data.due_date)
            updates["due_date"] = data.due_date

        if data.reminder_at is not None:
            if data.reminder_at == "":
                updates["reminder_at"] = None
            else:
                parsed_reminder = self._validate_reminder_at(data.reminder_at)
                updates["reminder_at"] = parsed_reminder.isoformat()

        if data.status is not None:
            updates["status"] = data.status.value

        if data.tags is not None:
            updates["tags"] = _normalize_tags(data.tags)

        if data.subtasks is not None:
            updates["subtasks"] = _normalize_subtasks(data.subtasks)

        if data.folder_id is not None:
            updates["folder_id"] = data.folder_id or None

        if data.position is not None:
            updates["position"] = int(data.position)

        # Recurrence transitions
        rec_changed = data.recurrence is not None
        new_rec = data.recurrence.value if rec_changed else record.get("recurrence", Recurrence.NONE.value)
        if rec_changed:
            updates["recurrence"] = new_rec
            if new_rec == Recurrence.NONE.value:
                updates["recurrence_until"] = None
                updates["recurrence_count"] = None
                updates["recurrence_series_id"] = None
            else:
                # turning recurrence on -> fresh series id (only when previously none)
                if record.get("recurrence", Recurrence.NONE.value) == Recurrence.NONE.value:
                    updates["recurrence_series_id"] = str(uuid.uuid4())

        if data.recurrence_until is not None:
            updates["recurrence_until"] = data.recurrence_until or None
        if data.recurrence_count is not None:
            updates["recurrence_count"] = data.recurrence_count

        # Re-validate recurrence bounds against effective values
        effective_rec = updates.get("recurrence", record.get("recurrence", Recurrence.NONE.value))
        if effective_rec != Recurrence.NONE.value:
            eff_due = updates.get("due_date", record.get("due_date"))
            if not eff_due:
                raise ValidationError(
                    [{"field": "due_date", "message": "Recurring todos require a due_date"}]
                )
            self._validate_recurrence_bounds(
                updates.get("recurrence_until", record.get("recurrence_until")),
                updates.get("recurrence_count", record.get("recurrence_count")),
                eff_due,
            )

        updates["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Detect status transition to done for spawn-next
        was_done = record.get("status") == Status.DONE.value
        will_be_done = updates.get("status") == Status.DONE.value if "status" in updates else was_done
        transitioning_to_done = (not was_done) and will_be_done

        records = self.todo_store.read_all()
        idx = next((i for i, r in enumerate(records) if r.get("id") == todo_id), None)
        if idx is None:
            raise NotFoundError("Todo not found")

        # Capture old due/reminder for series-cascade delta math
        old_due = record.get("due_date")
        old_reminder = record.get("reminder_at")

        records[idx].update(updates)
        updated_record = records[idx]

        # Apply-to-series cascade onto future occurrences
        if apply_to == "series":
            series_id = updated_record.get("recurrence_series_id")
            if series_id:
                target_index = updated_record.get("recurrence_index", 0)
                for i, r in enumerate(records):
                    if (
                        r.get("id") != todo_id
                        and r.get("recurrence_series_id") == series_id
                        and r.get("recurrence_index", 0) > target_index
                    ):
                        merged = {
                            k: v for k, v in updates.items()
                            if k not in ("due_date", "reminder_at")
                        }
                        # apply due/reminder as deltas
                        if "due_date" in updates and old_due and updates["due_date"]:
                            try:
                                from datetime import date as _d, timedelta as _td
                                delta_days = (_d.fromisoformat(updates["due_date"]) - _d.fromisoformat(old_due)).days
                                if r.get("due_date"):
                                    new_d = _d.fromisoformat(r["due_date"]) + _td(days=delta_days)
                                    merged["due_date"] = new_d.isoformat()
                            except (ValueError, TypeError):
                                pass
                        if "reminder_at" in updates and old_reminder and updates.get("reminder_at"):
                            try:
                                old_rem_dt = datetime.fromisoformat(old_reminder if isinstance(old_reminder, str) else old_reminder.isoformat())
                                new_rem_dt = datetime.fromisoformat(updates["reminder_at"])
                                delta = new_rem_dt - old_rem_dt
                                cur = r.get("reminder_at")
                                if cur:
                                    merged["reminder_at"] = (datetime.fromisoformat(cur) + delta).isoformat()
                            except (ValueError, TypeError):
                                pass
                        # never overwrite per-occurrence identity
                        for k in ("id", "created_at", "recurrence_index", "recurrence_series_id", "position"):
                            merged.pop(k, None)
                        records[i].update(merged)

        # Spawn next occurrence atomically when transitioning to done
        if (
            transitioning_to_done
            and updated_record.get("recurrence", Recurrence.NONE.value) != Recurrence.NONE.value
        ):
            next_row = self._build_next_occurrence(updated_record)
            if next_row:
                records.append(next_row)

        self.todo_store.write_all(records)
        return Todo(**updated_record)

    def delete(self, user_id: str, todo_id: str, apply_to: str = "occurrence") -> int:
        """Delete a todo. With ``apply_to=series`` removes future occurrences too.

        Returns the number of todos removed.
        """
        if apply_to not in ("occurrence", "series"):
            raise ValidationError(
                [{"field": "apply_to", "message": "apply_to must be 'occurrence' or 'series'"}]
            )

        record = self.todo_store.find_by_id(todo_id)
        if not record or record.get("user_id") != user_id:
            raise NotFoundError("Todo not found")

        if (
            apply_to == "series"
            and record.get("recurrence_series_id")
            and record.get("recurrence", Recurrence.NONE.value) != Recurrence.NONE.value
        ):
            series_id = record["recurrence_series_id"]
            target_index = record.get("recurrence_index", 0)
            records = self.todo_store.read_all()
            survivors = [
                r for r in records
                if not (
                    r.get("recurrence_series_id") == series_id
                    and r.get("user_id") == user_id
                    and r.get("recurrence_index", 0) >= target_index
                )
            ]
            removed = len(records) - len(survivors)
            self.todo_store.write_all(survivors)
            return removed

        deleted = self.todo_store.delete(todo_id)
        if not deleted:
            raise NotFoundError("Todo not found")
        return 1

    def reorder(self, user_id: str, ordered_ids: list[str]) -> list[Todo]:
        """Persist a manual ordering for the given todo ids.

        Each id in ``ordered_ids`` must belong to ``user_id``; ids not in the
        list keep their existing position. Returns the user's todos in the new
        order.
        """
        records = self.todo_store.read_all()
        owned_ids = {r["id"] for r in records if r.get("user_id") == user_id}
        unknown = [tid for tid in ordered_ids if tid not in owned_ids]
        if unknown:
            raise NotFoundError("One or more todos not found")

        rank = {tid: idx for idx, tid in enumerate(ordered_ids)}
        for r in records:
            if r["id"] in rank:
                r["position"] = rank[r["id"]]
        self.todo_store.write_all(records)
        return self.list_todos(user_id=user_id, sort_by="position")

    def add_time(self, user_id: str, todo_id: str, seconds: int) -> Todo:
        """Add ``seconds`` to a todo's ``time_spent_seconds`` (Pomodoro)."""
        if seconds < 0:
            raise ValidationError([{"field": "seconds", "message": "seconds must be >= 0"}])
        record = self.todo_store.find_by_id(todo_id)
        if not record or record.get("user_id") != user_id:
            raise NotFoundError("Todo not found")
        new_total = int(record.get("time_spent_seconds") or 0) + int(seconds)
        updated = self.todo_store.update(
            todo_id,
            {
                "time_spent_seconds": new_total,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return Todo(**updated)

    def set_image(self, user_id: str, todo_id: str, image_url: str | None) -> Todo:
        """Attach (or detach) an image URL to a todo."""
        record = self.todo_store.find_by_id(todo_id)
        if not record or record.get("user_id") != user_id:
            raise NotFoundError("Todo not found")
        updated = self.todo_store.update(
            todo_id,
            {
                "image_url": image_url,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return Todo(**updated)

    def bulk_action(
        self,
        user_id: str,
        ids: list[str],
        action: str,
        payload: dict | None,
        folder_store: JSONStore | None = None,
    ) -> dict:
        """Apply ``action`` across many todo ids in a single atomic write.

        Returns ``{ outcomes, summary }``. Per-id statuses are one of
        ``succeeded``, ``not_found``, ``no_change``, ``validation_error``.
        """
        valid_actions = {
            "mark_done", "mark_pending", "mark_in_progress", "delete",
            "move_to_folder", "add_tag", "remove_tag", "set_priority",
        }
        if action not in valid_actions:
            raise ValidationError(
                [{"field": "action", "message": f"Invalid action: {action}"}]
            )

        payload = payload or {}
        # Pre-validate payload
        target_folder_id: str | None = None
        if action == "move_to_folder":
            raw = payload.get("folder_id")
            if raw in (None, ""):
                target_folder_id = None
            else:
                target_folder_id = str(raw)
                if folder_store is not None:
                    f = folder_store.find_by_id(target_folder_id)
                    if not f or f.get("user_id") != user_id:
                        raise ValidationError(
                            [{"field": "folder_id", "message": "Folder not found"}]
                        )
        target_tag: str | None = None
        if action in ("add_tag", "remove_tag"):
            raw = payload.get("tag")
            if not isinstance(raw, str):
                raise ValidationError(
                    [{"field": "tag", "message": "tag must be a string"}]
                )
            target_tag = raw.strip().lower()
            if not target_tag:
                raise ValidationError(
                    [{"field": "tag", "message": "tag must not be empty"}]
                )
        target_priority: str | None = None
        if action == "set_priority":
            raw = payload.get("priority")
            if raw not in {p.value for p in Priority}:
                raise ValidationError(
                    [{"field": "priority", "message": "priority must be low|medium|high"}]
                )
            target_priority = raw

        # Dedup ids preserving order
        seen: set[str] = set()
        unique_ids: list[str] = []
        for raw_id in ids:
            if not isinstance(raw_id, str):
                continue
            if raw_id in seen:
                continue
            seen.add(raw_id)
            unique_ids.append(raw_id)

        records = self.todo_store.read_all()
        by_id = {r.get("id"): r for r in records}

        outcomes: dict[str, dict] = {}
        now = datetime.now(timezone.utc).isoformat()

        # Track delete + spawn-next per series to enforce "once per series"
        delete_ids: set[str] = set()
        spawn_per_series: dict[str, dict] = {}  # series_id -> source row (highest index)

        for tid in unique_ids:
            row = by_id.get(tid)
            if not row or row.get("user_id") != user_id:
                outcomes[tid] = {"status": "not_found"}
                continue
            if action == "delete":
                delete_ids.add(tid)
                outcomes[tid] = {"status": "succeeded"}
                continue
            changed = False
            if action == "mark_done":
                if row.get("status") != Status.DONE.value:
                    was_done = False
                    row["status"] = Status.DONE.value
                    row["updated_at"] = now
                    changed = True
                    # candidate for series spawn
                    sid = row.get("recurrence_series_id")
                    rec = row.get("recurrence", Recurrence.NONE.value)
                    if sid and rec != Recurrence.NONE.value and not was_done:
                        cur = spawn_per_series.get(sid)
                        if cur is None or row.get("recurrence_index", 0) > cur.get("recurrence_index", 0):
                            spawn_per_series[sid] = row
            elif action == "mark_pending":
                if row.get("status") != Status.PENDING.value:
                    row["status"] = Status.PENDING.value
                    row["updated_at"] = now
                    changed = True
            elif action == "mark_in_progress":
                if row.get("status") != Status.IN_PROGRESS.value:
                    row["status"] = Status.IN_PROGRESS.value
                    row["updated_at"] = now
                    changed = True
            elif action == "move_to_folder":
                if (row.get("folder_id") or None) != target_folder_id:
                    row["folder_id"] = target_folder_id
                    row["updated_at"] = now
                    changed = True
            elif action == "add_tag":
                tags = list(row.get("tags") or [])
                if target_tag in tags:
                    pass
                else:
                    tags.append(target_tag)
                    row["tags"] = tags
                    row["updated_at"] = now
                    changed = True
            elif action == "remove_tag":
                tags = list(row.get("tags") or [])
                if target_tag in tags:
                    row["tags"] = [t for t in tags if t != target_tag]
                    row["updated_at"] = now
                    changed = True
            elif action == "set_priority":
                if row.get("priority") != target_priority:
                    row["priority"] = target_priority
                    row["updated_at"] = now
                    changed = True
            outcomes[tid] = {"status": "succeeded" if changed else "no_change"}

        # apply deletes
        if delete_ids:
            records = [r for r in records if r.get("id") not in delete_ids]

        # spawn next for done recurring (once per series)
        for source in spawn_per_series.values():
            nxt = self._build_next_occurrence(source)
            if nxt:
                records.append(nxt)

        self.todo_store.write_all(records)

        summary = {
            "total": len(unique_ids),
            "succeeded": sum(1 for o in outcomes.values() if o["status"] == "succeeded"),
            "not_found": sum(1 for o in outcomes.values() if o["status"] == "not_found"),
            "forbidden": 0,
            "validation_error": sum(1 for o in outcomes.values() if o["status"] == "validation_error"),
            "no_change": sum(1 for o in outcomes.values() if o["status"] == "no_change"),
        }
        return {"outcomes": outcomes, "summary": summary}

    def list_tags(self, user_id: str) -> list[dict]:
        """Return distinct tags used by the user with usage counts."""
        records = [r for r in self.todo_store.read_all() if r.get("user_id") == user_id]
        counts: dict[str, int] = {}
        for r in records:
            for tag in r.get("tags") or []:
                counts[tag] = counts.get(tag, 0) + 1
        return [
            {"name": name, "count": count}
            for name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ]


    def get_stats(self, user_id: str) -> TodoStats:
        """Compute dashboard statistics for the user.

        Computes total, completed, pending, and overdue counts.
        Overdue = due_date before today AND status != done.

        Args:
            user_id: The authenticated user's ID.

        Returns:
            TodoStats with computed counts.
        """
        all_records = self.todo_store.read_all()
        user_todos = [r for r in all_records if r.get("user_id") == user_id]

        total = len(user_todos)
        completed = sum(1 for r in user_todos if r.get("status") == Status.DONE.value)
        pending = sum(1 for r in user_todos if r.get("status") in (Status.PENDING.value, Status.IN_PROGRESS.value))

        today = date.today()
        overdue = 0
        for r in user_todos:
            due = r.get("due_date")
            if due and r.get("status") != Status.DONE.value:
                try:
                    due_date = date.fromisoformat(due)
                    if due_date < today:
                        overdue += 1
                except (ValueError, TypeError):
                    pass

        return TodoStats(total=total, completed=completed, pending=pending, overdue=overdue)

    def _validate_recurrence_bounds(
        self,
        recurrence_until: str | None,
        recurrence_count: int | None,
        due_date: str,
    ) -> None:
        if recurrence_until is not None and recurrence_count is not None:
            raise ValidationError(
                [{"field": "recurrence_until", "message": "Only one of recurrence_until or recurrence_count may be set"}]
            )
        if recurrence_until is not None:
            self._validate_due_date(recurrence_until)
            if recurrence_until <= due_date:
                raise ValidationError(
                    [{"field": "recurrence_until", "message": "recurrence_until must be after due_date"}]
                )
        if recurrence_count is not None:
            try:
                count_int = int(recurrence_count)
            except (TypeError, ValueError):
                raise ValidationError(
                    [{"field": "recurrence_count", "message": "recurrence_count must be an integer"}]
                )
            if count_int <= 0 or count_int > 1000:
                raise ValidationError(
                    [{"field": "recurrence_count", "message": "recurrence_count must be 1..1000"}]
                )

    def _build_next_occurrence(self, source_row: dict) -> dict | None:
        """Compute and return the next-occurrence row, or None if capped."""
        recurrence = source_row.get("recurrence", Recurrence.NONE.value)
        due_date = source_row.get("due_date")
        if recurrence == Recurrence.NONE.value or not due_date:
            return None

        try:
            next_due = next_occurrence_date(due_date, recurrence)
        except ValueError:
            return None

        rec_until = source_row.get("recurrence_until")
        if rec_until and next_due > rec_until:
            return None

        cur_index = int(source_row.get("recurrence_index") or 0)
        new_index = cur_index + 1
        rec_count = source_row.get("recurrence_count")
        if rec_count is not None and new_index >= int(rec_count):
            return None

        new_reminder = None
        if source_row.get("reminder_at"):
            try:
                rem_str = source_row["reminder_at"]
                if isinstance(rem_str, datetime):
                    rem_str = rem_str.isoformat()
                new_reminder = shift_reminder(rem_str, due_date, next_due)
            except (ValueError, TypeError):
                new_reminder = None

        # reset subtasks done flags
        new_subtasks = []
        for st in source_row.get("subtasks") or []:
            new_subtasks.append({
                "id": str(uuid.uuid4()),
                "title": st.get("title", ""),
                "done": False,
            })

        return {
            "id": str(uuid.uuid4()),
            "user_id": source_row["user_id"],
            "title": source_row.get("title", ""),
            "description": source_row.get("description"),
            "priority": source_row.get("priority", Priority.MEDIUM.value),
            "due_date": next_due,
            "reminder_at": new_reminder,
            "status": Status.PENDING.value,
            "folder_id": source_row.get("folder_id"),
            "tags": list(source_row.get("tags") or []),
            "subtasks": new_subtasks,
            "image_url": None,
            "position": int(source_row.get("position", 0)),
            "time_spent_seconds": 0,
            "comments": [],
            "recurrence": recurrence,
            "recurrence_until": rec_until,
            "recurrence_count": rec_count,
            "recurrence_series_id": source_row.get("recurrence_series_id"),
            "recurrence_index": new_index,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }

    def _validate_due_date(self, due_date: str) -> None:
        """Validate that due_date is a valid ISO 8601 date (YYYY-MM-DD).

        Args:
            due_date: The date string to validate.

        Raises:
            ValidationError: If the date format is invalid.
        """
        # Check format with regex first
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", due_date):
            raise ValidationError(
                [{"field": "due_date", "message": "Invalid date format. Must be YYYY-MM-DD"}]
            )

        # Verify it's a valid date
        try:
            date.fromisoformat(due_date)
        except ValueError:
            raise ValidationError(
                [{"field": "due_date", "message": "Invalid date format. Must be YYYY-MM-DD"}]
            )

    def _validate_reminder_at(self, reminder_at: str) -> datetime:
        """Validate that reminder_at is a valid ISO 8601 datetime string.

        Args:
            reminder_at: The datetime string to validate.

        Returns:
            The parsed datetime object.

        Raises:
            ValidationError: If the datetime format is invalid.
        """
        try:
            parsed = datetime.fromisoformat(reminder_at)
            return parsed
        except (ValueError, TypeError):
            raise ValidationError(
                [{"field": "reminder_at", "message": "Invalid datetime format. Must be ISO 8601 (e.g. 2025-01-15T09:00:00)"}]
            )
