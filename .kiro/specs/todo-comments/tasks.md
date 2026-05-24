# Implementation Plan: Todo Comments

## Overview

Implements threaded comments on todos with @mentions and image attachments, per `requirements.md` and `design.md`. The work splits into:

- Backend foundations: extend the Todo model, add Comment + Attachment models, build the mention extractor.
- Attachment subsystem: registry, upload endpoint, orphan sweep.
- Comment subsystem: service, router, user-search endpoint for autocomplete.
- Frontend: Pinia store, recursive thread component, comment input with mention autocomplete and attachment uploads, integration into the todo edit modal.
- End-to-end wiring + verification.

Property tests reference Properties 1-15 in `design.md`.

## Tasks

- [ ] 1. Backend foundations: models and mention extractor
  - [ ] 1.1 Extend `models.py` with `Attachment`, `Comment`, `MentionRef`, `CommentResponse`, `CommentCreate`, `CommentUpdate`; add `comments: list[Comment] = []` to `Todo`
    - Default `comments` to `[]` when reading a Todo record without the key (handled by Pydantic default; verify in test)
    - Set `Comment.body` to `min_length=1, max_length=2000`; `attachment_ids` to `max_length=4` on DTOs
    - Add `is_tombstone: bool = False` on `Comment`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.5, 5.7_

  - [ ] 1.2 Implement `services/mention_extractor.py` with `extract_mention_usernames(body) -> list[str]`
    - Strip backtick-delimited code spans before matching
    - Use regex `(?<![A-Za-z0-9_])@([A-Za-z0-9_]{3,30})(?![A-Za-z0-9_])`
    - Deduplicate while preserving first-appearance order
    - _Requirements: 4.1, 4.2_

  - [ ]* 1.3 Property tests for mention extractor
    - **Property 6: Mention dedup and order preservation**
    - **Property 7: Code-span exclusion**
    - Strategy: build random bodies with k mentions interleaved with non-mention `@`-strings, optionally wrapped in backticks
    - **Validates: Requirements 4.1, 4.2**

- [ ] 2. Attachment subsystem
  - [ ] 2.1 Implement `JSONStore`-backed attachment registry at `data/attachments.json`
    - Create the file with `[]` if missing, reusing the existing `JSONStore` atomic write
    - _Requirements: 5.1, 5.2_

  - [ ] 2.2 Implement `services/attachment_service.py` with `upload`, `bind_to_comment`, `unbind_from_comment`, `delete_unreferenced`, `sweep_orphans`
    - Validate MIME against `ALLOWED_MIME_TYPES = {png, jpeg, gif, webp}`
    - Validate size against `MAX_BYTES = 5 MB`
    - Write files to `data/uploads/comments/<uuid>.<ext>` and return server-relative URL `/uploads/comments/<uuid>.<ext>`
    - Sanitize original filename (strip path components, limit length)
    - `bind_to_comment` is idempotent on edit (already bound to this comment_id is allowed)
    - `sweep_orphans` deletes registry entries and files for unbound attachments older than 1 hour
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [ ] 2.3 Implement `routers/attachments.py` with `POST /api/comment-attachments` and `DELETE /api/comment-attachments/{id}`
    - Authenticated via `get_current_user`
    - Multipart upload returns 201 with the Attachment object
    - DELETE only succeeds for unbound attachments owned by the caller (404 otherwise)
    - Wire `app.mount("/uploads", StaticFiles(directory="data/uploads"))` in `main.py`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ] 2.4 Wire attachment orphan sweep into `main.py` startup
    - `asyncio.create_task` running every 600 seconds
    - Log sweep count at info level
    - _Requirements: 5.8_

  - [ ]* 2.5 Property tests for attachment service
    - **Property 9: Attachment ownership** — `bind_to_comment` rejects ids not owned by caller; store unchanged on rejection
    - **Property 10: Attachment type/size enforcement** — invalid uploads neither write a file nor register an attachment
    - **Validates: Requirements 5.3, 5.4, 5.6**

- [ ] 3. Comment subsystem
  - [ ] 3.1 Implement `services/comment_service.py` with `list_comments`, `create_comment`, `update_comment`, `delete_comment`, internal `_depth`, `_resolve_mentions`
    - Verify todo ownership via the existing pattern (404 on miss)
    - For replies: validate `parent_comment_id` exists on the same Todo; compute depth via `_depth` with cycle detection (visited set)
    - Body validation per Pydantic + explicit whitespace-only rejection
    - On create/update: extract mentions, resolve to existing Users, dedupe ids
    - On update: author-only (404 otherwise); set `updated_at`; ignore attempts to change `parent_comment_id`, `author_id`, `todo_id`, `created_at`
    - On delete: tombstone if any other comment has `parent_comment_id == this.id`; otherwise hard-delete; call `attachment_service.delete_unreferenced` on hard-delete
    - Atomic write via `JSONStore.update` on the parent Todo
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 4.6, 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.4, 10.4_

  - [ ] 3.2 Implement `routers/comments.py` mounted under todos: GET/POST `/api/todos/{id}/comments`, PUT/DELETE `/api/todos/{id}/comments/{cid}`
    - All endpoints require `get_current_user`
    - Status codes: 200 (GET, PUT), 201 (POST), 204 (DELETE)
    - Map `ValidationError` -> 422, `NotFoundError` -> 404 via existing handlers
    - _Requirements: 2.1, 6.1, 7.1, 8.1_

  - [ ] 3.3 Implement `routers/users.py` with `GET /api/users/search?q=<prefix>`
    - Authenticated; case-insensitive prefix match on `username`; cap 8 results
    - Returns `[{id, username}]` only (no email, no created_at)
    - Reject empty `q` with 422
    - _Requirements: 4.5, 9.4_

  - [ ]* 3.4 Property tests for comment service
    - **Property 1: Comment ownership isolation**
    - **Property 2: Author-only edit/delete**
    - **Property 3: Thread depth bound**
    - **Property 4: Cycle-free parent chain** (relies on parent_comment_id immutability + depth check)
    - **Property 5: Mention extraction is body-text-only**
    - **Property 8: Attachment count bound** (>4 attachment_ids -> 422, store unchanged)
    - **Property 11: Tombstone preserves thread structure**
    - **Property 12: Hard-delete removes record and unreferenced attachments**
    - **Property 13: Comment round-trip**
    - **Property 14: Backward-compatible read** (Todo without `comments` key reads as `comments == []`)
    - **Property 15: Mention resolution is total over known users**
    - Strategies: `todo_with_comments` builds an acyclic depth<=5 tree; `body_with_known_and_unknown_mentions`
    - **Validates: Requirements 1.4, 2.3, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 5.6, 5.7, 5.8, 6.2, 7.2, 7.3, 7.4, 8.2, 10.2, 10.4**

- [ ] 4. Backend integration tests (example-based)
  - [ ] 4.1 Router-level tests via FastAPI `TestClient`
    - Full happy path: upload 2 attachments -> create comment with mentions -> reply -> edit -> delete (tombstone) -> hard-delete leaf
    - Permission paths: another user's todo (404), another user's comment edit (404)
    - Validation paths: empty body, oversize body, parent on different todo, depth-6 reply, 5th attachment, unknown attachment id, mention to unknown user (resolves to empty mentions, comment still created)
    - _Requirements: covers all router behaviors_

- [ ] 5. Backend checkpoint
  - Run pytest suite; ensure no regressions in existing `test_*` files
  - Tag commit `unit-todo-comments-backend`

- [ ] 6. Frontend foundations
  - [ ] 6.1 Extend `types/index.ts` with `Attachment`, `MentionRef`, `Comment` interfaces
    - Mirror backend `CommentResponse` shape (denormalized mentions)
    - _Requirements: 1.2_

  - [ ] 6.2 Implement `stores/comments.ts` (Pinia)
    - State: `byTodoId`, `loading`, `error`
    - Actions: `fetch(todoId)`, `create(todoId, dto)` (optimistic), `update(todoId, cid, dto)` (optimistic), `remove(todoId, cid)` (optimistic with tombstone fallback)
    - Rollback on failure with toast
    - _Requirements: 9.7_

  - [ ] 6.3 Implement `composables/useComments.ts`
    - Wraps the store with derived getters: `topLevel(todoId)`, `repliesOf(commentId)`, `depthOf(commentId)`
    - Provides upload helper that calls the attachment endpoint and tracks pending uploads
    - _Requirements: 9.1, 9.5_

- [ ] 7. Frontend components
  - [ ] 7.1 Implement `components/comments/AttachmentPreview.vue`
    - Thumbnail with optional remove button; supports both composing and rendering modes
    - Click opens lightbox (reuse existing image viewer if present, else a simple modal)
    - _Requirements: 5.5, 9.2, 9.5_

  - [ ] 7.2 Implement `components/comments/MentionAutocomplete.vue`
    - Floating list bound to a textarea, shown when caret is in an `@<prefix>` token
    - Calls `GET /api/users/search?q=<prefix>` with 200ms debounce; caps 8 results
    - Insert on Enter / click; Esc dismisses
    - _Requirements: 9.4, 4.5_

  - [ ] 7.3 Implement `components/comments/CommentInput.vue`
    - Textarea + attachment picker (drag-drop or click) + submit button
    - Wires `MentionAutocomplete`
    - Tracks `attachment_ids` from `useComments.upload`; shows previews with remove control
    - Disabled while submitting; emits `submit({ body, parent_comment_id, attachment_ids })`
    - Surfaces upload size/type errors as toasts and excludes failed files from submission
    - _Requirements: 5.5, 9.5, 9.6_

  - [ ] 7.4 Implement `components/comments/CommentItem.vue`
    - Renders avatar placeholder, `author_username`, relative `created_at`, body
    - Body renderer replaces `@username` tokens with styled links when the resolved id appears in `mentions`; unresolved tokens render as plain text
    - Renders attachments inline (uses `AttachmentPreview`)
    - Author-only edit/delete buttons; reply button visible when depth < 5
    - Tombstone state: shows `[deleted]` styled, hides actions
    - _Requirements: 4.5, 9.2, 9.3, 7.2_

  - [ ] 7.5 Implement `components/comments/CommentThread.vue` (recursive)
    - Props: `todoId`, `parentCommentId | null`, `depth`
    - Renders all comments where `parent_comment_id === parentCommentId`, ordered by `created_at` asc
    - Self-recurses with `depth + 1` for replies; stops past `MAX_THREAD_DEPTH = 5`
    - Inline reply input scoped to the targeted comment
    - _Requirements: 9.1, 9.3, 3.5_

  - [ ] 7.6 Wire comments into the existing todo edit modal (`TodoForm.vue`)
    - "Comments" section visible only when editing an existing todo
    - Mounts `<CommentThread :todoId="todo.id" :parentCommentId="null" :depth="1" />` and a top-level `<CommentInput>`
    - Calls `useComments.fetch(todo.id)` on mount
    - _Requirements: 9.1_

- [ ] 8. Frontend checkpoint
  - Manual smoke test: full create → reply → edit → tombstone → hard-delete flow
  - Verify image upload and inline rendering
  - Verify mention autocomplete trigger and link rendering
  - Tag commit `unit-todo-comments-frontend`

- [ ] 9. End-to-end verification and polish
  - [ ] 9.1 Verify backwards compatibility on existing `todos.json`
    - Existing user data without `comments` keys reads cleanly
    - Edit on a legacy todo persists `comments: []` on next write
    - _Requirements: 1.4, 5.2, 10.2_

  - [ ] 9.2 Verify attachment orphan sweep
    - Upload an attachment, do not bind it, fast-forward time (override `max_age_seconds=1` in a test) and confirm the file and registry entry are gone
    - _Requirements: 5.8_

  - [ ] 9.3 Update root `README.md` with the new endpoints
    - Add comments endpoints and `POST /api/comment-attachments` to the API table
    - Mention `/uploads/comments/*` static path
    - _Requirements: documentation only_

  - [ ]* 9.4 Frontend unit tests for components
    - `CommentThread.vue` recursive rendering at depths 1, 3, 5; tombstone branch
    - `CommentInput.vue` mention autocomplete trigger + attachment preview list
    - `useComments` optimistic create + rollback on failure
    - _Requirements: 9.1, 9.3, 9.5, 9.7_

- [ ] 10. Final checkpoint
  - Run backend pytest, frontend smoke test
  - Confirm no regressions in `test_todo_service`, `test_auth_service`, etc.
  - Tag commit `unit-todo-comments-complete`

## Notes

- Tasks marked with `*` are property/unit tests. Skipping them yields a faster MVP but loses the correctness guarantees.
- The `attachments.json` registry is per-app-instance, not per-user. Ownership is enforced in service-layer checks.
- The user-search endpoint (`/api/users/search`) is added here because mention autocomplete requires it. It's intentionally narrow (prefix-only, capped, returns `{id, username}` only) to avoid leaking PII.
- Threads and mentions are functional but produce no novel behavior in the current single-user app. They become meaningful when folder-sharing is added in a later unit.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1"] },
    { "id": 2, "tasks": ["2.2"] },
    { "id": 3, "tasks": ["2.3", "2.4", "2.5", "3.1", "3.3"] },
    { "id": 4, "tasks": ["3.2", "3.4", "6.1"] },
    { "id": 5, "tasks": ["4.1", "6.2"] },
    { "id": 6, "tasks": ["5", "6.3"] },
    { "id": 7, "tasks": ["7.1", "7.2"] },
    { "id": 8, "tasks": ["7.3", "7.4"] },
    { "id": 9, "tasks": ["7.5"] },
    { "id": 10, "tasks": ["7.6"] },
    { "id": 11, "tasks": ["8", "9.1", "9.2", "9.3"] },
    { "id": 12, "tasks": ["9.4"] },
    { "id": 13, "tasks": ["10"] }
  ]
}
```
