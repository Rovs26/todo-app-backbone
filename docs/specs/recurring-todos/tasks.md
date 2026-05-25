# Implementation Plan: Recurring Todos

## Overview

Adds the `recurrence`, `recurrence_until`, `recurrence_count`, `recurrence_series_id`, `recurrence_index` fields to the Todo model and implements done-transition spawning, series edit/delete, and frontend authoring/display per `requirements.md` and `design.md`. Property tests reference Properties 1-13 in `design.md`.

## Tasks

- [ ] 1. Backend foundations: enums, models, helper
  - [ ] 1.1 Add `Recurrence` enum and recurrence fields to `Todo`, `TodoCreate`, `TodoUpdate` in `models.py`
    - Defaults: `recurrence=NONE`, `recurrence_until=None`, `recurrence_count=None`, `recurrence_series_id=None`, `recurrence_index=0`
    - `recurrence_count` bounded `ge=1, le=1000` at the model level
    - Pydantic backward-compat: missing fields read as defaults
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [ ] 1.2 Implement `services/recurrence_helper.py` with `shift_date`, `shift_datetime`, `should_spawn_next`, `build_next_occurrence`
    - Use `dateutil.relativedelta` for DST/leap-year correctness
    - `shift_date(Jan 31, monthly) == Feb 28/29` (clamped)
    - `shift_datetime` preserves wall-clock time
    - `should_spawn_next` returns False when recurrence==none, due_date is None, count cap reached, or until cap exceeded
    - `build_next_occurrence` resets subtask `done` flags, clears `comments`, `image_url`, `time_spent_seconds`, sets `status=pending`
    - Add `python-dateutil` to `requirements.txt` if not present
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 5.1, 5.2_

  - [ ]* 1.3 Property tests for `recurrence_helper`
    - **Property 5: Date shift correctness** (matrix of edge dates: Jan 31, Mar 31, Feb 29, end-of-month boundaries)
    - **Property 6: Reminder shift preserves wall-clock time**
    - **Validates: Requirements 4.4, 4.5**

- [ ] 2. Backend service: validation, spawn, series operations
  - [ ] 2.1 Add `_validate_recurrence_fields` to `TodoService` and call from `create` and `update`
    - Reject invalid enum, missing due_date when recurring, both bounds set, until <= due_date, count out of range
    - When recurrence is set to `NONE`, clear `recurrence_until`, `recurrence_count`, `recurrence_series_id` on the persisted record
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ] 2.2 Update `TodoService.create` to set `recurrence_series_id` and `recurrence_index`
    - When `recurrence != NONE`, set `recurrence_series_id` to a fresh UUID4 and `recurrence_index` to 0
    - When `recurrence == NONE`, set `recurrence_series_id` to `None`
    - When created already with `status==done` and `recurrence!=none`, spawn the first next occurrence atomically
    - _Requirements: 3.1, 3.2, 6.4_

  - [ ] 2.3 Update `TodoService.update` to detect not-done -> done transitions and spawn the next occurrence atomically
    - Detect transition by comparing stored status with effective new status
    - On transition, call `should_spawn_next`; if true, build next occurrence and add it to the same `write_all` batch as the updated current occurrence
    - Idempotent: re-saving a done todo or toggling done off and back on does not produce additional spawns
    - Handle the recurrence-transition cases: none -> non-none assigns fresh series_id; non-none -> none clears series fields on the affected record only
    - _Requirements: 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 5.3, 5.4, 6.1, 6.2, 6.3_

  - [ ] 2.4 Implement `apply_to=series` for `TodoService.update`
    - Compute due_date and reminder_at deltas on the target
    - Apply non-date field updates verbatim to all occurrences with the same `recurrence_series_id` and `recurrence_index > target.index`
    - Apply due_date and reminder_at as deltas (preserving each occurrence's offset)
    - Preserve per-occurrence `id`, `created_at`, `recurrence_index`, `recurrence_series_id`, `position`
    - _Requirements: 7.1, 7.2, 7.4_

  - [ ] 2.5 Implement `apply_to=series` for `TodoService.delete`
    - Default behavior unchanged when `apply_to=occurrence` (or omitted)
    - With `apply_to=series` and target.recurrence != none, delete target plus all occurrences with same `recurrence_series_id` and `recurrence_index >= target.index`; past occurrences untouched
    - _Requirements: 8.1, 8.2_

  - [ ] 2.6 Add `recurrence` filter to `TodoService.list_todos`
    - Optional parameter; reject values outside `{none, daily, weekly, monthly, yearly}` with 422
    - Preserve existing status/priority/sort_by behavior
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 2.7 Property tests for service-level recurrence behavior
    - **Property 1: Recurrence input validation rejection**
    - **Property 2: Series id lifecycle**
    - **Property 3: Spawn on done-transition is exactly-once**
    - **Property 4: No spawn for non-recurring or capped series**
    - **Property 7: Next occurrence inherits template fields**
    - **Property 8: User isolation extends to series**
    - **Property 9: Series edit preserves per-occurrence identity**
    - **Property 10: Series delete affects only target and future**
    - **Property 11: Atomic done + spawn** (simulate I/O error mid-write)
    - **Property 12: Recurrence round-trip**
    - **Property 13: Backward-compatible read**
    - **Validates: Requirements 1.6, 2.1-2.6, 3.1-3.4, 4.1-4.7, 5.1-5.4, 6.1-6.4, 7.1-7.4, 8.1-8.2, 11.2, 11.3, 11.4**

- [ ] 3. Backend router updates
  - [ ] 3.1 Add `apply_to` query parameter to `PUT /api/todos/{id}` and `DELETE /api/todos/{id}` in `routers/todos.py`
    - Validate `apply_to` is `occurrence` or `series`; default `occurrence`
    - Pass through to service
    - _Requirements: 7.3, 8.3_

  - [ ] 3.2 Add `recurrence` query parameter to `GET /api/todos`
    - Pass through to service; reject invalid values with 422
    - _Requirements: 9.2, 9.3_

- [ ] 4. Backend integration tests
  - [ ] 4.1 Router-level tests via `TestClient`
    - Create recurring todo -> mark done -> verify next occurrence appears via `GET /api/todos?recurrence=...`
    - Capped series: count=3 stops after the 3rd done; until-bounded series stops when next due_date > until
    - Edit `apply_to=series`: future occurrences updated, past occurrences untouched
    - Delete `apply_to=series`: future occurrences gone, past preserved
    - Validation errors for invalid combinations and `apply_to` values
    - _Requirements: covers all router behaviors_

- [ ] 5. Backend checkpoint
  - Run pytest; ensure no regressions
  - Tag commit `unit-recurring-todos-backend`

- [ ] 6. Frontend foundations
  - [ ] 6.1 Extend `types/index.ts` with `Recurrence` type and Todo recurrence fields
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ] 6.2 Update `stores/todos.ts`: extend `updateTodo` and `deleteTodo` with optional `applyTo` argument
    - Pass `?apply_to=...` to API calls
    - On `apply_to=series`, optimistic patch covers all in-store todos with matching `recurrence_series_id`; on failure, refetch
    - After done-transition on a recurring todo, call `fetchTodos()` to pick up the new occurrence
    - _Requirements: 7.1, 7.2, 8.1, 8.2, 10.7_

  - [ ] 6.3 Add `recurrence` to filter state and `FilterBar.vue`
    - Optional dropdown: All, None, Daily, Weekly, Monthly, Yearly
    - _Requirements: 9.2, 9.4_

- [ ] 7. Frontend components
  - [ ] 7.1 Update `components/TodoForm.vue` with recurrence selector and end-condition fields
    - Recurrence dropdown (None / Daily / Weekly / Monthly / Yearly)
    - When recurrence != None, show "Ends on" date picker and "After N occurrences" numeric input; only one enabled at a time
    - Require `due_date` when recurrence != None; show inline error when missing
    - Block submission with field-level error if invalid
    - _Requirements: 10.1, 10.2, 10.3_

  - [ ] 7.2 Update `components/TodoItem.vue` to display the recurrence badge
    - Small circular-arrow icon + label visible when `recurrence != 'none'`
    - Hover tooltip describes cadence and end condition
    - _Requirements: 10.4_

  - [ ] 7.3 Implement `components/RecurrenceApplyToToggle.vue` (radio control)
    - Options: "This occurrence" (default) and "This and future occurrences"
    - Emits selected value
    - _Requirements: 10.5, 10.6_

  - [ ] 7.4 Wire `RecurrenceApplyToToggle` into the edit modal and the delete `ConfirmDialog`
    - Visible only when the target todo is recurring
    - Save button reads the toggle and passes `applyTo` to the store action
    - _Requirements: 10.5, 10.6_

- [ ] 8. Frontend checkpoint
  - Manual smoke test: create a daily recurring todo with due_date, mark done, verify next occurrence in list
  - Verify capped series (count=2) stops after the second completion
  - Verify edit `apply_to=series` propagates a title change to future occurrences
  - Verify delete `apply_to=series` removes future, preserves past
  - Tag commit `unit-recurring-todos-frontend`

- [ ] 9. Polish and documentation
  - [ ] 9.1 Update root `README.md` with new Todo fields and `apply_to` query parameter
    - Mention `recurrence` filter on GET /api/todos
    - _Requirements: documentation only_

  - [ ]* 9.2 Frontend unit tests
    - `TodoForm.recurrence.spec.ts`: end-condition mutual exclusion, required due_date enforcement
    - `TodoItem.recurrence.spec.ts`: badge visibility and tooltip
    - Store update with `applyTo='series'` performs optimistic batch patch and refetches on failure
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [ ] 10. Final checkpoint
  - Run backend pytest, frontend smoke tests
  - Confirm no regressions in earlier specs (notably `todo-comments`)
  - Tag commit `unit-recurring-todos-complete`

## Notes

- Tasks marked with `*` are property/unit tests; skipping them yields a faster MVP without correctness guarantees.
- This spec touches the same Todo model as `todo-comments`. The two specs are designed to be additive: `comments` and `recurrence_*` fields don't conflict. Implementation order should be: `todo-comments` first (since it changes the comment-bearing data shape), then `recurring-todos`.
- `python-dateutil` is added as a backend dependency (likely already present transitively, but pin it explicitly).
- `subtasks` are treated as part of the template per Requirement 4.3. If you later add per-occurrence subtasks, that semantic will need a follow-up spec.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3"] },
    { "id": 3, "tasks": ["2.4", "2.5", "2.6"] },
    { "id": 4, "tasks": ["2.7", "3.1", "3.2", "6.1"] },
    { "id": 5, "tasks": ["4.1", "6.2"] },
    { "id": 6, "tasks": ["5", "6.3"] },
    { "id": 7, "tasks": ["7.1", "7.2", "7.3"] },
    { "id": 8, "tasks": ["7.4"] },
    { "id": 9, "tasks": ["8", "9.1"] },
    { "id": 10, "tasks": ["9.2"] },
    { "id": 11, "tasks": ["10"] }
  ]
}
```
