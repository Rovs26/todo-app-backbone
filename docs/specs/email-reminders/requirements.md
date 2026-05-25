# Requirements Document

## Introduction

Sends email reminders to users when one of their todos hits its `reminder_at` time. The backend runs a scheduler that polls for due reminders, dispatches an email through SMTP, marks the reminder sent so it never fires twice, and retries transient failures. Users can opt out per-account. When SMTP is not configured (e.g., local dev), the system logs reminders to a file instead of failing.

This spec absorbs the earlier `todo-reminders` draft (the `reminder_at` field is already in `models.py`). It extends the existing `fullstack-todo-app` and `todo-comments` and `recurring-todos` specs without conflict.

## Glossary

- **Reminder**: A todo with a non-null `reminder_at` whose moment has arrived.
- **EmailService**: Service that builds and sends the email body, abstracted over an SMTP backend and a no-op file-logger backend.
- **ReminderScheduler**: Asyncio task running on the backend that polls for due reminders every 60 seconds.
- **SMTP backend**: Real outbound delivery via `smtplib`, configured by `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, optional `SMTP_USE_TLS` (default true).
- **File-log backend**: Fallback when SMTP env vars are missing; appends a JSON line per "sent" reminder to `data/email_log.jsonl`.
- **reminder_send_log**: A separate JSON file `data/reminder_send_log.json` recording every send attempt with status, attempt count, and timestamp.
- **Lead time**: The delta between `reminder_at` and the moment the email is dispatched. Lead time should normally be < 60 s (one polling cycle); the requirement is that no reminder fires before its `reminder_at`.

## Requirements

### Requirement 1: Reminder dispatch fields on Todo

**User Story:** As the system, I need to track which reminders have already been dispatched, so that no reminder fires twice.

#### Acceptance Criteria

1. THE Todo model SHALL include a field `reminder_sent` whose value is a boolean defaulting to `false`.
2. THE Todo model SHALL include an optional field `reminder_sent_at` whose value is either an ISO 8601 datetime or `null`, defaulting to `null`.
3. WHEN a Todo is read from `todos.json` and does not contain `reminder_sent` or `reminder_sent_at`, THE Backend SHALL treat the missing fields as `false` and `null` respectively.
4. WHEN a Todo's `reminder_at` is updated to a new value via PUT, THE Todo_Service SHALL reset `reminder_sent` to `false` and `reminder_sent_at` to `null` so the new reminder time can fire.
5. WHEN a Todo's `reminder_at` is cleared (set to null) via PUT, THE Todo_Service SHALL also reset `reminder_sent` to `false` and `reminder_sent_at` to `null`.
6. THE addition of these fields SHALL NOT alter the validation, defaults, or behavior of any other Todo field.

### Requirement 2: Per-user opt-in/out

**User Story:** As a user, I want to control whether the system sends me reminder emails.

#### Acceptance Criteria

1. THE User model SHALL include a field `email_reminders_enabled` whose value is a boolean defaulting to `true`.
2. WHEN a User is read from `users.json` without this field, THE Backend SHALL treat it as `true` (preserving the default-on behavior for legacy accounts).
3. WHEN a `PUT /api/auth/me` request is received from an authenticated user with body `{ "email_reminders_enabled": <bool> }`, THE Auth_Service SHALL update the user's preference and return the updated user payload.
4. WHEN the ReminderScheduler considers a due reminder, IF the owning user's `email_reminders_enabled` is `false`, THEN THE ReminderScheduler SHALL skip that reminder, mark `reminder_sent` to `true` and `reminder_sent_at` to the skip timestamp, and record an entry in `reminder_send_log` with status `skipped_optout`.
5. THE addition of this field SHALL NOT alter the existing behavior of `GET /api/auth/me` (which already returns `id`, `email`, `username`, `created_at`); the field SHALL be added to the response.

### Requirement 3: Reminder scheduler polling

**User Story:** As the system, I need to find due reminders quickly so users get them on time.

#### Acceptance Criteria

1. WHEN the FastAPI app starts, THE Backend SHALL launch a ReminderScheduler asyncio task that runs continuously until shutdown.
2. THE ReminderScheduler SHALL poll for due reminders every 60 seconds (±5 seconds tolerance, to allow for jitter).
3. THE ReminderScheduler SHALL consider a Todo "due for dispatch" when all of the following are true: `reminder_at != null`, `reminder_at <= now (UTC)`, `reminder_sent == false`.
4. THE ReminderScheduler SHALL NOT dispatch a reminder for a Todo whose `reminder_at` is in the future at the moment of polling.
5. WHEN the FastAPI app shuts down, THE ReminderScheduler SHALL stop its loop within 5 seconds, completing any in-flight dispatch.
6. THE ReminderScheduler SHALL handle exceptions inside the polling loop without exiting (catch + log; resume next cycle).

### Requirement 4: Email content and rendering

**User Story:** As a user, I want the reminder email to include the todo's title, due date, and a link, so that I can act on it without opening the app first.

#### Acceptance Criteria

1. THE EmailService SHALL build each reminder email with: a subject of the form `Reminder: <todo title>` (trimmed and truncated to 80 characters), a plain-text body, and an HTML body.
2. THE plain-text body SHALL include: the todo's title, the formatted `due_date` (or "No due date") and `priority`, the formatted `reminder_at` time in UTC, and a link to the dashboard `${FRONTEND_URL}/dashboard`.
3. THE HTML body SHALL render the same content with simple inline styles (no images, no external CSS).
4. THE EmailService SHALL set the `From` header to `SMTP_FROM` and the `To` header to the user's `email`.
5. WHEN building the email, THE EmailService SHALL escape any HTML-special characters in user-supplied text (title, description) before inserting them into the HTML body.

### Requirement 5: SMTP and fallback backends

**User Story:** As a developer, I want reminders to work without configuring SMTP locally, so that I can test the flow without secrets.

#### Acceptance Criteria

1. WHEN the backend starts AND all required SMTP env vars (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`) are present and non-empty, THE EmailService SHALL use the SMTP backend.
2. WHEN any required SMTP env var is missing, THE EmailService SHALL use the file-log backend.
3. WHEN using the SMTP backend, THE EmailService SHALL connect via `smtplib.SMTP_SSL` if `SMTP_USE_TLS=true` (default) or `smtplib.SMTP` with `STARTTLS` if `SMTP_USE_TLS=starttls`, authenticate, and send.
4. WHEN using the file-log backend, THE EmailService SHALL append one JSON line per email to `data/email_log.jsonl` with fields: `timestamp`, `to`, `subject`, `text_body`, `html_body`. THE file-log backend SHALL never raise.
5. THE backend choice SHALL be logged once at startup at INFO level, including the chosen backend's name and the masked `SMTP_HOST` (if SMTP).
6. THE EmailService SHALL accept an explicit injected backend (for tests).

### Requirement 6: Retry and failure handling

**User Story:** As the system, I need to recover from transient SMTP failures without losing reminders or duplicating them.

#### Acceptance Criteria

1. WHEN the EmailService send call raises an exception, THE ReminderScheduler SHALL retry up to 2 additional times with exponential backoff: 5 s, 25 s.
2. THE ReminderScheduler SHALL count the original attempt as attempt 1; total attempts SHALL be at most 3.
3. WHEN all 3 attempts fail, THE ReminderScheduler SHALL set `reminder_sent = true` and `reminder_sent_at = now`, AND record an entry in `reminder_send_log` with status `failed` plus the last exception's class name and message (truncated to 500 characters).
4. WHEN any attempt succeeds, THE ReminderScheduler SHALL set `reminder_sent = true` and `reminder_sent_at = now`, AND record an entry in `reminder_send_log` with status `sent` and the attempt number.
5. THE ReminderScheduler SHALL NOT block its 60 s poll cycle waiting for retries; retries SHALL run on a per-reminder asyncio task while the next cycle continues.
6. IF a process restarts mid-retry, THE on-disk state SHALL ensure no duplicate sends: the affected reminder SHALL appear in the next cycle as still `reminder_sent == false` and SHALL be retried as a fresh dispatch.

### Requirement 7: Rate limiting

**User Story:** As the system, I need a global cap so that an unexpected backlog of reminders does not flood the SMTP server.

#### Acceptance Criteria

1. THE ReminderScheduler SHALL dispatch at most 100 reminder emails in any rolling 60-second window across all users.
2. WHEN the cap is reached during a polling cycle, THE ReminderScheduler SHALL defer remaining due reminders to the next cycle without marking them sent.
3. WHEN deferring, THE ReminderScheduler SHALL log a single warning per cycle indicating the count deferred.
4. THE 100/60s cap SHALL be configurable via env var `REMINDER_RATE_LIMIT_PER_MINUTE` with default 100.

### Requirement 8: Reminder send log

**User Story:** As an operator (or developer), I want a record of every reminder attempt so I can debug missed deliveries.

#### Acceptance Criteria

1. THE ReminderScheduler SHALL persist every reminder attempt to `data/reminder_send_log.json` as an array of objects.
2. Each log entry SHALL contain: `id` (UUID4), `todo_id`, `user_id`, `email`, `attempted_at` (ISO 8601), `status` (one of `sent`, `failed`, `skipped_optout`, `skipped_user_missing`), `attempt_count` (1–3), and optional `error_class` and `error_message` (only for `failed`).
3. THE log SHALL use the existing JSONStore atomic write to avoid corruption.
4. THE log SHALL be cap-trimmed: when the file grows beyond 10 000 entries, the oldest 1 000 entries SHALL be discarded on the next write.
5. IF the user referenced by a due reminder no longer exists, THEN THE ReminderScheduler SHALL record a `skipped_user_missing` entry, set `reminder_sent = true` on the orphan todo, and skip dispatch.

### Requirement 9: API endpoint for the user preference

**User Story:** As a user, I want to update my email-reminder preference through the API.

#### Acceptance Criteria

1. WHEN a `PUT /api/auth/me` request is received with body `{"email_reminders_enabled": <bool>}` from an authenticated user, THE Auth_Service SHALL update the User record and return the updated user payload (id, email, username, created_at, email_reminders_enabled).
2. IF the request body contains fields other than `email_reminders_enabled`, THEN THE Auth_Service SHALL ignore those fields (do not allow updates to email/username via this endpoint).
3. IF the request body is empty or `email_reminders_enabled` is missing, THEN THE Auth_Service SHALL return a 422 validation error.
4. THE existing `GET /api/auth/me` SHALL include `email_reminders_enabled` in its response.

### Requirement 10: Frontend settings UI

**User Story:** As a user, I want a simple toggle in the app to control email reminders.

#### Acceptance Criteria

1. THE Frontend SHALL include a settings section accessible from the dashboard header (e.g., a gear icon) that exposes an "Email reminders" toggle bound to `email_reminders_enabled`.
2. WHEN the toggle is changed, THE Frontend SHALL call `PUT /api/auth/me` with the new value and SHALL display a toast on success or failure.
3. THE settings section SHALL show the user's current email address and indicate that emails will be sent there.
4. WHEN the user account is loaded (`GET /api/auth/me`), THE Frontend SHALL initialize the toggle from `email_reminders_enabled`.

### Requirement 11: Privacy and data isolation

**User Story:** As a user, I want my reminders processed without leaking my data to other users.

#### Acceptance Criteria

1. THE ReminderScheduler SHALL include user-id ownership when reading the dispatch log for any user-facing endpoint.
2. THE current spec SHALL NOT expose any reminder log endpoint to authenticated users; the log is server-side only.
3. WHEN the EmailService writes to the file-log backend, THE log file path SHALL be inside `backend/data/` and SHALL NOT be served by the StaticFiles mount (which only serves `data/uploads/`).
4. THE existing user-isolation guarantees (Property 9 in `fullstack-todo-app`) SHALL apply unchanged.

### Requirement 12: Persistence and integrity

**User Story:** As the system, I need reminder state changes to be durable so I do not double-send across restarts.

#### Acceptance Criteria

1. WHEN the ReminderScheduler marks `reminder_sent = true` after a successful send, THE write to `todos.json` SHALL be atomic (existing JSONStore guarantee).
2. WHEN multiple reminders are processed within a polling cycle, the scheduler SHALL persist `reminder_sent` for each one individually after dispatch (not in a single bulk write at end of cycle), to bound the duplicate-send window during a crash to a single reminder.
3. FOR ALL valid Todo objects with non-default `reminder_sent` and `reminder_sent_at`, serializing to JSON and deserializing back SHALL produce an equivalent Todo (round-trip property).
