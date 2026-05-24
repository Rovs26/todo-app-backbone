# Requirements Document

## Introduction

Adds bulk actions on the todo list. The user can select multiple todos with checkboxes and apply a single action across all selections at once: mark done, mark pending, delete, move to folder, add tag, remove tag, set priority. The backend exposes a single bulk endpoint that returns a per-id outcome map so the frontend can show partial-success states. All operations are scoped to the authenticated user; ids belonging to other users return `not_found` per the existing isolation pattern.

This spec extends the existing `fullstack-todo-app` (and is additive to `todo-comments` and `recurring-todos`). It does not replace any existing single-todo endpoint.

## Glossary

- **Bulk Action**: One of the supported operations applied to a set of todo ids in a single request.
- **Outcome**: The per-id result of a bulk action: `succeeded`, `not_found`, `forbidden`, `validation_error`, `no_change`.
- **Selection**: The set of todo ids the user has currently checked in the UI.
- **MAX_BULK_IDS**: 200. Maximum number of ids in a single bulk request.

## Requirements

### Requirement 1: Bulk endpoint contract

**User Story:** As an authenticated user, I want a single API call that applies one action across many todos, so that I do not have to issue dozens of requests.

#### Acceptance Criteria

1. WHEN a `POST /api/todos/bulk` request is received with body `{ ids: string[], action: string, payload?: object }`, THE Todo_Service SHALL execute the action against every id and return a per-id outcome map plus a summary count.
2. THE response body SHALL have shape `{ outcomes: Record<string, { status, error?: string }>, summary: { total, succeeded, not_found, forbidden, validation_error, no_change } }`.
3. THE response status SHALL be 200 even when some ids fail individually; only request-level errors (malformed body, unknown action, oversize batch) return 4xx.
4. THE Todo_Service SHALL preserve the input id order in the `outcomes` map iteration order (best-effort; clients should not rely on JS object ordering for correctness).
5. IF the request body is missing `ids`, missing `action`, or contains a non-string id, THEN THE Todo_Service SHALL return a 422 validation error.
6. IF `ids` is empty, THEN THE Todo_Service SHALL return a 422 validation error indicating at least one id is required.
7. IF `ids` contains more than MAX_BULK_IDS entries, THEN THE Todo_Service SHALL return a 413 payload-too-large error.
8. IF `ids` contains duplicate values, THEN THE Todo_Service SHALL deduplicate and process each id at most once; the outcomes map SHALL contain each unique id once.

### Requirement 2: Supported actions

**User Story:** As a user, I want a useful set of bulk actions covering the most common multi-todo operations.

#### Acceptance Criteria

1. THE Todo_Service SHALL accept the following `action` values: `mark_done`, `mark_pending`, `mark_in_progress`, `delete`, `move_to_folder`, `add_tag`, `remove_tag`, `set_priority`.
2. IF `action` is any other value, THEN THE Todo_Service SHALL return a 422 validation error identifying `action` as the invalid field.
3. WHEN `action` is `mark_done`, `mark_pending`, or `mark_in_progress`, THE Todo_Service SHALL set `status` to the corresponding value on each owned todo, set `updated_at` to the current timestamp, and SHALL NOT modify any other field.
4. WHEN `action` is `delete`, THE Todo_Service SHALL remove each owned todo from the store; the outcome status SHALL be `succeeded` for each id removed.
5. WHEN `action` is `move_to_folder` AND `payload.folder_id` is a string referring to a folder owned by the authenticated user, THE Todo_Service SHALL set `folder_id` to that value on each owned todo. WHEN `payload.folder_id` is `null` or empty, THE Todo_Service SHALL clear `folder_id` (move out of any folder).
6. WHEN `action` is `add_tag` AND `payload.tag` is a non-empty string, THE Todo_Service SHALL append the tag to each owned todo's `tags` array if and only if it is not already present (set semantics).
7. WHEN `action` is `remove_tag` AND `payload.tag` is a non-empty string, THE Todo_Service SHALL remove the tag from each owned todo's `tags` array if present; if absent, the per-id outcome SHALL be `no_change`.
8. WHEN `action` is `set_priority` AND `payload.priority` is one of `low`, `medium`, `high`, THE Todo_Service SHALL set `priority` on each owned todo.
9. IF `payload` is missing or has the wrong shape for the chosen `action`, THEN THE Todo_Service SHALL return a 422 validation error before processing any id.

### Requirement 3: Per-id outcome rules

**User Story:** As a user, I want to know which items in a batch failed, so that I can act on them individually if needed.

#### Acceptance Criteria

1. WHEN an id refers to a todo owned by the authenticated user AND the action applies cleanly, THE outcome for that id SHALL be `succeeded`.
2. WHEN an id refers to a todo not owned by the authenticated user OR not present in the store, THE outcome for that id SHALL be `not_found` (matching the existing isolation pattern; not `forbidden`).
3. WHEN an id is syntactically invalid (e.g., not a UUID-like string), THE outcome for that id SHALL be `validation_error` with a brief error message; the request SHALL still proceed for valid ids.
4. WHEN the action would not change the stored value (e.g., `add_tag` for a tag already present, `mark_done` on a todo already done), THE outcome for that id SHALL be `no_change`.
5. THE Todo_Service SHALL NOT abort the bulk operation when an individual id fails; processing SHALL continue for remaining ids.

### Requirement 4: Atomicity and persistence

**User Story:** As a user, I want a bulk action to either fully apply or leave the store consistent, so that I never see partial state.

#### Acceptance Criteria

1. THE Todo_Service SHALL collect all changes in memory before issuing a single atomic `JSONStore.write_all` call for the bulk operation (existing atomic-write guarantee).
2. IF the write to `todos.json` fails (file system error), THEN THE Todo_Service SHALL return a 500 internal server error and the file SHALL remain in its prior valid state.
3. WHEN actions modify multiple todos, ALL modifications SHALL be reflected in the single write; THE Todo_Service SHALL NOT issue per-id writes for bulk operations.

### Requirement 5: Folder validation for move

**User Story:** As a user, I want bulk move-to-folder to fail safely when the target folder isn't valid.

#### Acceptance Criteria

1. WHEN `action == "move_to_folder"` AND `payload.folder_id` is non-null AND the folder does not exist in the store OR is not owned by the authenticated user, THEN THE Todo_Service SHALL return a 422 validation error before processing any id and SHALL NOT modify the store.
2. WHEN `payload.folder_id` is `null` or omitted, THE Todo_Service SHALL treat the action as "move out of folder" and apply it without folder validation.

### Requirement 6: Tag normalization

**User Story:** As a user, I want consistent tag handling so that case and whitespace differences do not produce duplicates.

#### Acceptance Criteria

1. WHEN `action == "add_tag"` or `action == "remove_tag"`, THE Todo_Service SHALL normalize `payload.tag` by stripping leading/trailing whitespace and lowercasing.
2. IF the normalized tag is empty (after stripping), THEN THE Todo_Service SHALL return a 422 validation error.
3. THE Todo_Service SHALL store and compare tags using the normalized form to enforce set semantics.

### Requirement 7: Recurring-todos interaction

**User Story:** As a user, I want bulk actions to behave predictably when applied to recurring todos.

#### Acceptance Criteria

1. WHEN `action == "mark_done"` includes a recurring todo (recurrence != none), THE Todo_Service SHALL trigger the same spawn-next-occurrence behavior as the single-todo update path (per the `recurring-todos` spec).
2. WHEN multiple recurring todos in the same series appear in `ids` for `mark_done`, THE Todo_Service SHALL spawn at most one next occurrence per distinct `recurrence_series_id` per request (the spawn fires for the highest `recurrence_index` in the series within the batch).
3. WHEN `action == "delete"` includes recurring todos, THE Todo_Service SHALL delete only the specified ids; THE Todo_Service SHALL NOT cascade to other occurrences in the series (use the existing `apply_to=series` parameter on the single-todo DELETE for cascade semantics).

### Requirement 8: Frontend selection model

**User Story:** As a user, I want clear UI to select multiple todos and apply an action.

#### Acceptance Criteria

1. THE TodoList SHALL render a checkbox to the left of each visible todo when "select mode" is active.
2. THE TodoList header SHALL include a "select all visible" checkbox that toggles selection of all currently rendered todos (post-filter, post-sort).
3. WHEN one or more todos are selected, THE Frontend SHALL display a floating action bar fixed to the bottom of the viewport showing the selected count and action buttons.
4. THE floating action bar SHALL include buttons for: Mark done, Mark pending, Delete (with confirm), Move to folder (opens folder picker), Add tag (opens tag input), Remove tag (opens tag input), Set priority (opens priority picker).
5. WHEN the user clicks an action button, THE Frontend SHALL send a single `POST /api/todos/bulk` request with the selected ids; on response, THE Frontend SHALL refresh the todo list and display a toast summarizing the outcome (e.g., "12 done, 1 not found").
6. IF the action requires a payload (folder, tag, priority), THE Frontend SHALL prompt the user via a small popover before issuing the request.
7. WHEN the user navigates away or clears the selection, THE Frontend SHALL exit select mode.

### Requirement 9: Frontend optimistic updates

**User Story:** As a user, I want bulk actions to feel responsive even on a slow network.

#### Acceptance Criteria

1. WHEN a bulk action is dispatched, THE Frontend SHALL apply optimistic changes to the local store (e.g., status flip, tag add) before the server response arrives.
2. WHEN the response arrives, THE Frontend SHALL reconcile the local state against the per-id outcomes: ids with `succeeded` keep optimistic changes; ids with `not_found`, `forbidden`, or `validation_error` revert to their prior state.
3. IF the request fails entirely (network error, 4xx/5xx), THEN THE Frontend SHALL revert all optimistic changes and display an error toast.
4. THE Frontend SHALL skip optimistic update for `delete` to avoid a flash of removed-then-restored items; deletion SHALL apply only after server confirmation.

### Requirement 10: Performance bound

**User Story:** As a user, I want the UI to remain responsive when I select many todos.

#### Acceptance Criteria

1. WHEN selection size is at most MAX_BULK_IDS (200), THE Backend SHALL respond within 2 seconds at the 95th percentile under nominal load.
2. WHEN the user selects more than MAX_BULK_IDS, THE Frontend SHALL show a notice and disable the action buttons until selection is reduced. (The Backend would also reject; this prevents the round-trip.)
3. THE Frontend SHALL keep all checkbox toggles synchronous in the local store; selection state SHALL NOT depend on server round-trips.

### Requirement 11: Persistence and integrity

**User Story:** As a user, I want bulk-modified todos to round-trip cleanly through storage.

#### Acceptance Criteria

1. THE existing user-isolation guarantees (`fullstack-todo-app` Property 9) SHALL apply: a user SHALL NEVER affect another user's todos via the bulk endpoint.
2. FOR ALL valid Todo objects produced by a bulk action, the round-trip property (Property 15 of `fullstack-todo-app`) SHALL hold.
3. THE atomic-write guarantee SHALL hold for the bulk operation (Requirement 4.1).
