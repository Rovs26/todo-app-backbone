# Spec: SQLite Migration

Combined requirements + design + tasks. Replaces the JSON-file store with SQLite via SQLAlchemy. Foundational; touches every service.

## Goal

Move from `data/*.json` files to a single SQLite database for: concurrency safety (no file-level race), faster queries, and a base to grow into Postgres later.

## Requirements

### Requirement 1: Schema parity

#### Acceptance Criteria
1. THE SQLite schema SHALL preserve all current Pydantic fields on User, Todo, Folder, Notification, plus any added by prior specs (comments, attachments, recurrence, reminder_sent).
2. List fields (`tags`, `subtasks`, `mentions`, `attachments`) SHALL be stored as JSON columns to keep the migration scope contained (no need to design relational join tables for them in v1).
3. THE schema SHALL include indexes on: `todos.user_id`, `todos.folder_id`, `todos.status`, `notifications.user_id`, `folders.user_id`, `comments.todo_id`, `users.email`.

### Requirement 2: One-shot migration script

#### Acceptance Criteria
1. THE backend SHALL include `scripts/migrate_json_to_sqlite.py` that reads all `data/*.json` files and inserts rows into `data/app.db`.
2. THE script SHALL be idempotent: running it on an already-migrated DB SHALL skip rows whose primary key already exists and report the count.
3. THE script SHALL back up source files as `data/*.json.bak` before reading.
4. THE script SHALL emit a summary line per table.
5. IF a source row fails validation, THEN THE script SHALL log the failure and continue.

### Requirement 3: Service compatibility

#### Acceptance Criteria
1. EACH service (`auth_service`, `todo_service`, `folder_service`, `notification_service`, `comment_service` if landed) SHALL accept a SQLAlchemy `Session` factory instead of a `JSONStore`.
2. THE public method signatures of each service SHALL remain unchanged so callers (routers, scheduler, tests) need no edits.
3. THE existing pytest suite SHALL pass against the new SQLite-backed services with the only changes being fixture wiring.

### Requirement 4: Atomicity and isolation

#### Acceptance Criteria
1. EACH service method that performs multiple writes (e.g., bulk action, recurring spawn-next) SHALL wrap them in a single SQLAlchemy transaction.
2. User-ownership checks SHALL be enforced via `WHERE user_id = :user_id` in every query, matching the existing pattern.
3. THE app SHALL fail-fast if `data/app.db` cannot be opened or is in a corrupted state (no silent fallback to JSON).

### Requirement 5: Rollback path

#### Acceptance Criteria
1. THE migration script SHALL ship with a sibling `scripts/rollback_sqlite_to_json.py` that exports the SQLite DB back to JSON files matching the original shape, for one-step rollback.
2. THE rollback script SHALL also write `.bak` copies of any existing JSON files before overwriting.

## Design

- Dependency add: `sqlalchemy>=2.0`, no Alembic (single greenfield DB, no migrations beyond the initial schema).
- New `backend/db.py` with `engine`, `SessionLocal`, `Base`, and `get_session` dependency for FastAPI.
- New `backend/db_models.py` mirroring `models.py` Pydantic shapes as SQLAlchemy models. Pydantic models stay (for request/response validation); db_models are pure ORM.
- Each service grows a small `_to_pydantic(row)` helper.
- JSONStore stays in the codebase but is unused; mark deprecated in a docstring.
- The reminder scheduler and existing background tasks switch from reading JSON to opening a Session.

## Tasks

- [ ] 1. Schema and DB module
  - [ ] 1.1 Add `sqlalchemy` to `requirements.txt`
  - [ ] 1.2 Create `backend/db.py`: engine (`sqlite:///./data/app.db`), `SessionLocal`, `Base`, `get_session`
  - [ ] 1.3 Create `backend/db_models.py` with `UserRow`, `TodoRow`, `FolderRow`, `NotificationRow`, `CommentRow` (if comments shipped), `AttachmentRow` (if shipped)
  - [ ] 1.4 Add `init_db()` that calls `Base.metadata.create_all(engine)` on startup

- [ ] 2. Migration script
  - [ ] 2.1 `scripts/migrate_json_to_sqlite.py`
  - [ ] 2.2 Idempotency: check `existing_pk_set` before insert
  - [ ] 2.3 `.bak` copies before reading
  - [ ] 2.4 Summary printout
  - [ ]* 2.5 Test on a copy of current dev data

- [ ] 3. Service rewrites (one file at a time, smoke-test after each)
  - [ ] 3.1 `auth_service.py` → use Session
  - [ ] 3.2 `folder_service.py` → use Session
  - [ ] 3.3 `todo_service.py` → use Session (largest change)
  - [ ] 3.4 `notification_service.py` → use Session
  - [ ] 3.5 `comment_service.py` (if shipped) → use Session

- [ ] 4. Routers, scheduler, tests
  - [ ] 4.1 Update `dependencies.py` to provide a `Session` instead of JSONStore instances
  - [ ] 4.2 Update test fixtures to use an in-memory SQLite (`sqlite:///:memory:`)
  - [ ] 4.3 Reminder scheduler switches to Session
  - [ ] 4.4 Confirm pytest still 20+ passing

- [ ] 5. Rollback
  - [ ] 5.1 `scripts/rollback_sqlite_to_json.py`

- [ ] 6. Cleanup
  - [ ] 6.1 Mark `store.py` deprecated (docstring only — do not delete; some other code may import for type hints)
  - [ ] 6.2 Update README setup section

## Risks

- **Largest blast radius.** Every service touched. Mitigate by doing one service at a time + running the existing pytest suite between each.
- **Schema drift.** If any new field landed between the time this spec was written and execution time, the schema must reflect it. Migration script should grab all keys from each JSON record, not a hardcoded list.
- **JSON list columns.** Storing `tags`/`subtasks` as JSON loses the ability to filter "all todos with tag X" via SQL index. Acceptable for v1 (existing filters already iterate in Python). Note for follow-up.
