# Requirements Document

## Introduction

Adds recurring todos. A user can mark any todo as repeating on a daily, weekly, monthly, or yearly cadence; when the user marks the todo as done, the system automatically creates the next occurrence in the series with shifted `due_date` and `reminder_at`. Series can be bounded by an end date or a max occurrence count, or run indefinitely. Series share a `recurrence_series_id` so future "edit all" or "stop the series" features can target the whole group.

This spec extends the existing `fullstack-todo-app` spec; auth, ownership, validation, and persistence guarantees from that spec continue to apply unchanged.

## Glossary

- **Recurrence**: A pattern that causes a Todo to spawn its next occurrence when the current one is completed. One of `none`, `daily`, `weekly`, `monthly`, `yearly`.
- **Series**: A chain of todos linked by a shared `recurrence_series_id`, generated from the same template.
- **Template**: The first todo in a series. Subsequent occurrences inherit its title, description, priority, folder, tags, subtasks (cleared), and recurrence fields.
- **Series Cap**: A `recurrence_until` (date) or `recurrence_count` (integer) bound that ends a series.
- **DST-safe shift**: A date arithmetic that shifts by calendar days, weeks, months, or years rather than fixed 24-hour blocks, so an event scheduled for 9:00 AM stays at 9:00 AM through daylight-saving transitions.

## Requirements

### Requirement 1: Recurrence fields on Todo

**User Story:** As an authenticated user, I want each todo to optionally repeat on a schedule, so that recurring tasks regenerate themselves automatically.

#### Acceptance Criteria

1. THE Todo model SHALL include a field `recurrence` whose value is one of `none`, `daily`, `weekly`, `monthly`, `yearly`, defaulting to `none`.
2. THE Todo model SHALL include an optional field `recurrence_until` whose value is either a valid ISO 8601 date (YYYY-MM-DD) or `null`.
3. THE Todo model SHALL include an optional field `recurrence_count` whose value is either a positive integer or `null`.
4. THE Todo model SHALL include a field `recurrence_series_id` whose value is a string (UUID4) shared by all occurrences in the same series, or `null` for non-recurring todos (recurrence == `none`).
5. THE Todo model SHALL include a field `recurrence_index` whose value is a non-negative integer indicating the 0-based position of the occurrence in the series, defaulting to 0 for non-recurring todos and the template.
6. WHEN a Todo is read from `todos.json` and does not contain any of `recurrence`, `recurrence_until`, `recurrence_count`, `recurrence_series_id`, `recurrence_index`, THE Backend SHALL treat the missing fields as their defaults (`none`, `null`, `null`, `null`, `0` respectively).
7. THE addition of the recurrence fields SHALL NOT alter the validation, defaults, or behavior of any other Todo field.

### Requirement 2: Validation of recurrence input

**User Story:** As a user, I want recurrence input to be validated, so that the system catches mistakes before persisting them.

#### Acceptance Criteria

1. IF a create or update request includes a `recurrence` value not in `{none, daily, weekly, monthly, yearly}`, THEN THE Todo_Service SHALL return a 422 validation error identifying `recurrence` as the invalid field.
2. IF a create or update request sets `recurrence` to a value other than `none` AND `due_date` is not provided (and the todo currently has no `due_date`), THEN THE Todo_Service SHALL return a 422 validation error indicating that recurring todos require a `due_date`.
3. IF a create or update request includes both `recurrence_until` and `recurrence_count` set to non-null values, THEN THE Todo_Service SHALL return a 422 validation error indicating that only one of the two may be set.
4. IF a create or update request includes `recurrence_until` that is not a valid ISO 8601 date OR is on or before the resulting `due_date`, THEN THE Todo_Service SHALL return a 422 validation error.
5. IF a create or update request includes `recurrence_count` that is not a positive integer or that exceeds 1000, THEN THE Todo_Service SHALL return a 422 validation error.
6. IF a create or update request sets `recurrence` to `none`, THEN THE Todo_Service SHALL clear `recurrence_until`, `recurrence_count`, and `recurrence_series_id` to `null` on the persisted Todo (regardless of any non-null values supplied).

### Requirement 3: Series creation on first recurring todo

**User Story:** As a user, when I create a recurring todo, I want the series to be set up so future occurrences track back to it.

#### Acceptance Criteria

1. WHEN a create todo request is received with `recurrence != none`, THE Todo_Service SHALL set `recurrence_series_id` to a fresh UUID4 and `recurrence_index` to 0 on the created Todo.
2. WHEN a create todo request is received with `recurrence == none`, THE Todo_Service SHALL set `recurrence_series_id` to `null` and `recurrence_index` to 0 on the created Todo.
3. WHEN an update changes `recurrence` from `none` to a non-`none` value, THE Todo_Service SHALL set `recurrence_series_id` to a fresh UUID4 and SHALL keep `recurrence_index` at its current value (0 for the original todo).
4. WHEN an update changes `recurrence` from a non-`none` value to `none`, THE Todo_Service SHALL clear `recurrence_series_id` and series-bounding fields per Requirement 2.6 on the updated Todo only; existing past or future occurrences in the same series SHALL be unaffected by this update.

### Requirement 4: Spawning the next occurrence on completion

**User Story:** As a user, when I complete a recurring todo, I want the next occurrence to be created automatically.

#### Acceptance Criteria

1. WHEN a Todo with `recurrence != none` and a non-null `due_date` transitions to `status == done` (via create or update), THE Todo_Service SHALL create exactly one new Todo (the "next occurrence") with the following fields copied from the completed Todo: `user_id`, `title`, `description`, `priority`, `folder_id`, `tags`, `recurrence`, `recurrence_until`, `recurrence_count`, `recurrence_series_id`.
2. THE next occurrence SHALL have a fresh `id` (UUID4), a fresh `created_at` (current timestamp), `updated_at == null`, `status == pending`, `subtasks == []` (any `done` flags from the prior occurrence reset; if all subtasks shared, the next occurrence keeps them in pending state — see 4.3), and `comments == []`.
3. WHEN the completed Todo's `subtasks` are non-empty AND each subtask was originally part of the template, THE Todo_Service SHALL copy the subtasks onto the next occurrence with all `done` flags reset to `false`. (Subtasks added on a single occurrence — once per-occurrence subtasks exist — would not propagate; in this spec, all subtasks are treated as part of the template.)
4. THE next occurrence's `due_date` SHALL be the completed Todo's `due_date` shifted forward by exactly one recurrence interval, computed via DST-safe shift:
    - `daily`: +1 calendar day
    - `weekly`: +7 calendar days
    - `monthly`: +1 calendar month, clamped to the last day of the target month if the target day does not exist (e.g., Jan 31 + 1 month = Feb 28 or Feb 29)
    - `yearly`: +1 calendar year, clamped similarly (Feb 29 + 1 year = Feb 28 in non-leap years)
5. WHEN the completed Todo has a `reminder_at`, THE next occurrence's `reminder_at` SHALL be `reminder_at` plus the same calendar offset used for `due_date` (preserving wall-clock time of day in the original timezone of `reminder_at`).
6. THE next occurrence's `recurrence_index` SHALL be the completed Todo's `recurrence_index + 1`.
7. THE next occurrence's `position` SHALL equal the completed Todo's `position` (so the series stays in the same folder slot).

### Requirement 5: Series caps end the chain

**User Story:** As a user, I want recurring todos to stop spawning when they hit the end date or count I set.

#### Acceptance Criteria

1. IF the next occurrence's `due_date` would be after `recurrence_until` (when `recurrence_until` is non-null), THEN THE Todo_Service SHALL NOT create the next occurrence.
2. IF the next occurrence's `recurrence_index` would be greater than or equal to `recurrence_count` (when `recurrence_count` is non-null), THEN THE Todo_Service SHALL NOT create the next occurrence. Equivalently: a series with `recurrence_count = N` has occurrences indexed `0..N-1` inclusive.
3. WHEN the next occurrence is suppressed by 5.1 or 5.2, THE Todo_Service SHALL still mark the completed Todo as `done` (the suppression only affects the new occurrence, not the completion).
4. THE Todo_Service SHALL NOT modify or delete past occurrences when a series cap is reached.

### Requirement 6: Status transitions and idempotency

**User Story:** As a user, I want completing a recurring todo to spawn exactly one next occurrence, even if I toggle the status off and on.

#### Acceptance Criteria

1. WHEN a Todo's status transitions from `done` to a non-`done` value, THE Todo_Service SHALL NOT delete or alter any already-spawned next occurrence.
2. WHEN a Todo with `recurrence != none` is updated multiple times with `status == done` while it is already `done` (no transition), THE Todo_Service SHALL NOT create additional occurrences.
3. WHEN a Todo with `recurrence == none` transitions to `status == done`, THE Todo_Service SHALL NOT create a next occurrence.
4. WHEN a Todo with `recurrence != none` is created already in `status == done`, THE Todo_Service SHALL spawn the first next occurrence as defined in Requirement 4.

### Requirement 7: Editing recurring todos

**User Story:** As a user, when I edit a recurring todo, I want to know whether the edit applies to this occurrence or the whole series.

#### Acceptance Criteria

1. WHEN a `PUT /api/todos/{id}` request modifies a Todo with `recurrence != none`, THE Todo_Service SHALL apply the update only to the occurrence identified by `{id}`, leaving other occurrences in the same series unchanged.
2. WHEN the request includes a query parameter `apply_to=series` AND the requesting user owns the targeted Todo AND `recurrence != none`, THE Todo_Service SHALL additionally update all future occurrences in the same series (those with `recurrence_index > targetTodo.recurrence_index`) by applying the same field updates, except: `id`, `created_at`, `recurrence_index`, `recurrence_series_id`, `position` are preserved per occurrence; `due_date` and `reminder_at` updates SHALL be applied as deltas (the difference between old and new values on the target) rather than absolute values.
3. IF `apply_to` has any value other than `occurrence` (default) or `series`, THEN THE Todo_Service SHALL return a 422 validation error.
4. THE Todo_Service SHALL NOT retroactively modify past occurrences (those with `recurrence_index <= targetTodo.recurrence_index` excluding the target itself) regardless of `apply_to`.

### Requirement 8: Deleting recurring todos

**User Story:** As a user, when I delete a recurring todo, I want to choose between removing one occurrence or the rest of the series.

#### Acceptance Criteria

1. WHEN a `DELETE /api/todos/{id}` request is received without an `apply_to` parameter, THE Todo_Service SHALL delete only the occurrence identified by `{id}`.
2. WHEN a `DELETE /api/todos/{id}?apply_to=series` request is received AND the targeted Todo has `recurrence != none`, THE Todo_Service SHALL delete the targeted occurrence and all future occurrences in the same series (those with `recurrence_index >= targetTodo.recurrence_index`). Past occurrences SHALL NOT be deleted.
3. IF `apply_to` has any value other than `occurrence` (default) or `series`, THEN THE Todo_Service SHALL return a 422 validation error.

### Requirement 9: Listing recurring todos

**User Story:** As a user, I want recurring todos to appear in the list like any other todo, but distinguishable.

#### Acceptance Criteria

1. THE Todo_Service SHALL include all recurrence fields in every Todo returned by `GET /api/todos` and `GET /api/todos/{id}`.
2. THE GET /api/todos endpoint SHALL accept an optional query parameter `recurrence` whose valid values are `none`, `daily`, `weekly`, `monthly`, `yearly`; when provided, only todos matching that exact value SHALL be returned.
3. IF `recurrence` query parameter has a value not in the allowed set, THEN THE Todo_Service SHALL return a 422 validation error.
4. THE existing filtering and sorting behavior (status, priority, sort_by) SHALL continue to work unchanged when combined with `recurrence` filtering.

### Requirement 10: Frontend authoring and display

**User Story:** As a user, I want to set up and recognize recurring todos in the UI.

#### Acceptance Criteria

1. THE TodoForm component SHALL include a `recurrence` selector with options: None, Daily, Weekly, Monthly, Yearly.
2. WHEN `recurrence` is set to anything other than None, THE TodoForm SHALL show optional fields for "Ends on" (date picker, maps to `recurrence_until`) and "After N occurrences" (numeric input, maps to `recurrence_count`); only one of the two SHALL be enabled at a time.
3. THE TodoForm SHALL require `due_date` when `recurrence != None` and SHALL block submission with a field-level error if it is empty.
4. THE TodoItem component SHALL display a small recurrence badge (e.g., a circular-arrow icon with "Daily"/"Weekly"/etc.) when `recurrence != none`.
5. WHEN the user clicks the edit button on a recurring todo, THE Frontend SHALL show an "Apply to" toggle with options "This occurrence" (default) and "This and future occurrences" before saving.
6. WHEN the user clicks the delete button on a recurring todo, THE Frontend SHALL show a confirmation dialog with the same "Apply to" toggle before sending the delete request.
7. WHEN the user marks a recurring todo as done, THE Frontend SHALL refresh the todo list (the next occurrence appears automatically because the backend creates it).

### Requirement 11: Persistence and integrity

**User Story:** As a user, I want recurring todos to persist reliably and remain private to my account.

#### Acceptance Criteria

1. THE JSON_Store SHALL persist all recurrence fields inline on each Todo record in `todos.json`.
2. FOR ALL valid Todo objects with non-default recurrence fields, serializing to JSON and deserializing back SHALL produce an equivalent Todo with the same recurrence values (round-trip property).
3. THE existing user-isolation guarantees (Property 9 in `fullstack-todo-app`) SHALL apply to every occurrence in a series: a user SHALL only access occurrences whose `user_id` equals their own.
4. THE atomic-write guarantee (Property 18 in `fullstack-todo-app`) SHALL hold for the combined transaction of "mark current occurrence done + create next occurrence": both writes SHALL succeed together or `todos.json` SHALL remain in its prior valid state.
