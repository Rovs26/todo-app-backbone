# Implementation Plan: Bulk Actions

## Overview

Implements `POST /api/todos/bulk` plus selection-mode UI and floating action bar, per `requirements.md` and `design.md`. The bulk endpoint does one read, classifies and applies actions in memory, then issues one atomic write. The frontend gains a select mode with optimistic updates that reconcile against per-id outcomes.

## Tasks

- [ ] 1. Backend DTOs
  - [ ] 1.1 Add bulk request/response models to `models.py`
    - `BulkActionPayloadMove`, `BulkActionPayloadTag`, `BulkActionPayloadPriority`
    - `BulkActionRequest` with `ids: list[str]` (min 1, max 200), `action: Literal[...]`, `payload: dict | None`
    - `BulkOutcome { status: Literal["succeeded", "not_found", "forbidden", "validation_error", "no_change"], error: str | None }`
    - `BulkSummary { total, succeeded, not_found, forbidden, validation_error, no_change }`
    - `BulkActionResponse { outcomes: dict[str, BulkOutcome], summary: BulkSummary }`
    - _Requirements: 1.1, 1.2, 1.5, 1.6, 1.7_

- [ ] 2. TodoService.bulk
  - [ ] 2.1 Implement `TodoService.bulk(user_id, dto) -> BulkActionResponse`
    - Dedupe ids preserving order
    - Validate payload shape per action; reject early with `ValidationError`
    - For `move_to_folder` with non-null folder_id: verify folder ownership before any todo work
    - For `add_tag` / `remove_tag`: normalize via existing `_normalize_tags` (strip + lowercase)
    - Read all todos once; build `by_id` index; classify each id
    - Apply mutations in memory; track outcomes per id
    - For `mark_done` on recurring: collect spawn candidates, dedupe by `recurrence_series_id` keeping the highest `recurrence_index`, generate next occurrences via the recurring spec's `next_occurrence` helper (added later in recurring-todos)
    - Single `JSONStore.write_all` at end; return outcomes + summary
    - _Requirements: 2, 3, 4, 5, 6, 7_

  - [ ]* 2.2 Property tests for bulk service
    - **Atomicity**: failed validation → store unchanged
    - **Isolation**: ids belonging to other users return `not_found`; store unchanged
    - **Idempotency**: `add_tag` for present tag → `no_change`; `mark_done` on done → `no_change`
    - **Spawn-once**: bulk done on 5 occurrences of one series spawns exactly one next
    - _Requirements: 3, 7.2, 11_

- [ ] 3. Router
  - [ ] 3.1 Add `POST /api/todos/bulk` to `routers/todos.py`
    - Declared **before** `/{todo_id}` routes (existing router-order pattern)
    - Authenticated via `get_current_user`
    - Maps `ValidationError` → 422, oversize batch → 413
    - _Requirements: 1.1, 1.3, 1.7_

- [ ] 4. Frontend types and API
  - [ ] 4.1 Add `BulkAction`, `BulkOutcome`, `BulkSummary`, `BulkActionResponse`, `BulkActionRequest` to `types/index.ts`
  - [ ] 4.2 Add `todosApi.bulk(req)` to `utils/api.ts`

- [ ] 5. Frontend store
  - [ ] 5.1 Add `selectionIds: Set<string>`, `selectMode: boolean`, plus `toggleSelect`, `selectAllVisible`, `clearSelection`, `setSelectMode` to `stores/todos.ts`
  - [ ] 5.2 Add `bulk(action, payload?)` action: optimistic patch (except delete), POST, reconcile per-id, revert mismatches, toast summary
    - _Requirements: 9_

- [ ] 6. Frontend UI
  - [ ] 6.1 `components/BulkActionBar.vue`: floating bar with action buttons + count
  - [ ] 6.2 Per-row checkbox in `TodoItem.vue` (visible when `selectMode`)
  - [ ] 6.3 "Select all visible" checkbox in dashboard list header
  - [ ] 6.4 Payload popovers (folder picker, tag input, priority picker) inline in `BulkActionBar.vue`
  - [ ] 6.5 Confirm dialog for `delete` action
    - _Requirements: 8_

- [ ] 7. Verification
  - [ ] 7.1 Backend pytest passes; new bulk tests pass
  - [ ] 7.2 Manual smoke: select 3 todos, mark done, verify outcomes; select all, delete with confirm; bulk move to folder; bulk add/remove tag; bulk priority change
  - [ ] 7.3 Confirm no regressions in existing single-todo CRUD and recurring spawn (after recurring-todos lands)

## Notes

- The recurring spawn-once behaviour (task 2.1, fifth bullet) depends on the `next_occurrence` helper introduced in the `recurring-todos` spec. Bulk-actions implementation should land **after** recurring-todos so this branch isn't dead code.
- The folder ownership check for `move_to_folder` reuses the existing `folder_service.get_by_id(user, id)` pattern; no new helper needed.
- Optimistic delete is intentionally skipped (per Requirement 9.4) to avoid flash-of-removed-then-restored.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "3.1", "4.2"] },
    { "id": 3, "tasks": ["5.1"] },
    { "id": 4, "tasks": ["5.2", "6.1", "6.2", "6.3"] },
    { "id": 5, "tasks": ["6.4", "6.5"] },
    { "id": 6, "tasks": ["7.1", "7.2", "7.3"] }
  ]
}
```
