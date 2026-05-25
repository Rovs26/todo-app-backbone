# Implementation Plan: Email Reminders

## Overview

Implements server-side reminder dispatch via a polling scheduler, pluggable email backend (SMTP or file-log fallback), per-user opt-in/out, retry with backoff, rate limiting, and a frontend settings drawer per `requirements.md` and `design.md`. Property tests reference Properties 1-13 in `design.md`.

## Tasks

- [ ] 1. Backend models and configuration
  - [ ] 1.1 Add `reminder_sent: bool = False` and `reminder_sent_at: datetime | None = None` to `Todo`
    - Defaults handle backward-compat read of legacy records
    - _Requirements: 1.1, 1.2, 1.3, 1.6_

  - [ ] 1.2 Add `email_reminders_enabled: bool = True` to `User`; add to `UserResponse`
    - Add `UserPreferencesUpdate(BaseModel)` DTO
    - _Requirements: 2.1, 2.2, 2.5, 9.4_

  - [ ] 1.3 Update `TodoService.update` to reset `reminder_sent`/`reminder_sent_at` when `reminder_at` is set, modified, or cleared
    - When `reminder_at` field is not in the update DTO, leave sent state unchanged
    - _Requirements: 1.4, 1.5_

- [ ] 2. Email backend
  - [ ] 2.1 Implement `services/email_service.py` with `EmailBackend` Protocol, `SmtpBackend`, `FileLogBackend`, `EmailService`, and `build_email_service(env)` factory
    - `SmtpBackend` wraps `smtplib` in `asyncio.to_thread`; supports `SMTP_USE_TLS` in `{ssl, starttls, none}` (default `ssl`)
    - `FileLogBackend.send` writes one JSON line to `data/email_log.jsonl`; never raises (catches `OSError`, logs at error level)
    - `EmailService._render(todo)` returns `(subject, text, html)`; subject is `"Reminder: {title}"` truncated to 80 chars; HTML escapes user text via `html.escape`
    - `build_email_service(env)` selects SMTP if all `{SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM}` present, else FileLog
    - Log chosen backend at startup with masked host
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 2.2 Property tests for the email service
    - **Property 8: HTML body escapes user text**
    - **Property 9: Backend selection is deterministic from env**
    - **Validates: Requirements 4.5, 5.1, 5.2**

- [ ] 3. Reminder scheduler
  - [ ] 3.1 Implement `services/reminder_scheduler.py` with `ReminderScheduler` class
    - `run()` is the main loop: poll, then `await asyncio.wait_for(stop.wait(), timeout=60)`
    - `_select_due(now)` reads `todos.json` and returns todos matching `reminder_at != null AND reminder_at <= now AND not reminder_sent`
    - `_apply_rate_cap(due)` reads recent send-log timestamps to compute remaining headroom; returns up to (cap - already_sent_in_60s); logs deferred count when applicable
    - `_dispatch(todo, started_at)` is a per-reminder asyncio task: looks up user, branches into opt-out / missing-user / send paths, runs retries, persists outcome, appends log entry
    - Catches all per-cycle exceptions; loop survives transient errors
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.5_

  - [ ] 3.2 Implement send-log JSONStore wrapper at `data/reminder_send_log.json`
    - Reuse existing `JSONStore`
    - On append, if length > 10_000, drop the oldest 1_000 entries
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ] 3.3 Wire scheduler into `main.py` startup/shutdown hooks
    - On startup: build EmailService from env, construct ReminderScheduler, store on `app.state`, spawn task
    - On shutdown: call `stop()` then await the task with 5 s timeout
    - _Requirements: 3.1, 3.5_

  - [ ]* 3.4 Property tests for the scheduler
    - **Property 1: No reminder fires before its `reminder_at`**
    - **Property 2: Each reminder dispatches at most once**
    - **Property 3: Retry sequence is bounded** (use a backend that fails N times)
    - **Property 5: Opt-out short-circuits dispatch**
    - **Property 6: Missing user short-circuits dispatch**
    - **Property 7: Rate cap defers overflow**
    - **Property 13: Send log integrity**
    - Use `InMemoryBackend` and patched `asyncio.sleep` for retry timing
    - **Validates: Requirements 2.4, 3.3, 3.4, 6.1, 6.2, 6.3, 7.1, 7.2, 8.1, 8.2, 8.5**

- [ ] 4. Auth router and service for preferences
  - [ ] 4.1 Implement `AuthService.update_preferences(user_id, prefs)`
    - Returns updated User; raises NotFoundError if user missing
    - _Requirements: 9.1_

  - [ ] 4.2 Add `PUT /api/auth/me` endpoint that accepts `UserPreferencesUpdate`
    - Authenticated; ignores extra fields per Pydantic
    - Returns `UserResponse` including `email_reminders_enabled`
    - 422 on missing/invalid body
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ] 4.3 Update `GET /api/auth/me` to include `email_reminders_enabled`
    - _Requirements: 2.5, 9.4_

  - [ ]* 4.4 Property test for user isolation
    - **Property 10: User isolation in updates**
    - **Validates: Requirements 11.4**

- [ ] 5. Backend integration tests
  - [ ] 5.1 Router-level tests via `TestClient`
    - PUT /api/auth/me toggles preference; persists across re-fetch
    - GET /api/auth/me includes `email_reminders_enabled`
    - Reminder reset: PUT a todo with new `reminder_at` clears `reminder_sent`
    - Reminder reset: PUT a todo without `reminder_at` field preserves `reminder_sent`
    - _Requirements: covers all router behaviors_

  - [ ] 5.2 End-to-end scheduler test using `InMemoryBackend`
    - Seed two todos: one due, one future; advance time; assert one dispatch
    - Seed an opted-out user; assert skip + sent flag set
    - Seed a backend that fails twice then succeeds; assert 3rd attempt sent and log entry has `attempt_count=3`
    - _Requirements: 3.3, 6.1, 6.2, 6.3, 6.4_

- [ ] 6. Backend checkpoint
  - Run pytest; ensure no regressions
  - Tag commit `unit-email-reminders-backend`

- [ ] 7. Frontend
  - [ ] 7.1 Extend `types/index.ts` `User` with `email_reminders_enabled: boolean`
    - _Requirements: 2.1_

  - [ ] 7.2 Extend `stores/auth.ts` with `updatePreferences({ email_reminders_enabled })`
    - PUT /api/auth/me; patches `auth.user` on success; toast on success/failure
    - _Requirements: 10.2_

  - [ ] 7.3 Implement `components/SettingsDrawer.vue`
    - Drawer slides in from right; opened by gear icon in dashboard header
    - Section "Email reminders": toggle bound to `auth.user.email_reminders_enabled`; on change calls `updatePreferences`
    - Read-only display: "We'll send reminder emails to <email>"
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ] 7.4 Add a gear icon to the dashboard header that opens the settings drawer
    - _Requirements: 10.1_

- [ ] 8. Frontend checkpoint
  - Manual smoke test: open settings, toggle off, refresh, verify state persists
  - Tag commit `unit-email-reminders-frontend`

- [ ] 9. Polish and documentation
  - [ ] 9.1 Update root `README.md`
    - Document new env vars: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `SMTP_USE_TLS`, `FRONTEND_URL`, `REMINDER_RATE_LIMIT_PER_MINUTE`
    - Note that omitting SMTP vars triggers the file-log fallback
    - Document `PUT /api/auth/me`
    - _Requirements: documentation only_

  - [ ] 9.2 Update `.env.local.example` (or create) with the new env vars and dummy values
    - _Requirements: documentation only_

  - [ ]* 9.3 Frontend unit test
    - `SettingsDrawer.spec.ts`: toggle change calls `updatePreferences` with the new value
    - _Requirements: 10.2_

- [ ] 10. Final checkpoint
  - Run backend pytest and integration tests; manual frontend smoke test
  - Confirm no regressions in earlier specs (notably `recurring-todos`: a recurring todo's spawned next occurrence has `reminder_sent=false` so the scheduler picks up the new reminder)
  - Tag commit `unit-email-reminders-complete`

## Notes

- Tasks marked with `*` are property/unit tests; skipping them yields a faster MVP without correctness guarantees.
- Interaction with `recurring-todos`: when a recurring todo spawns its next occurrence, the new occurrence has default `reminder_sent=false`. No special-case wiring needed.
- File-log backend (`data/email_log.jsonl`) is intentionally not served by StaticFiles. Verify this in the smoke test.
- The scheduler runs in-process. If you ever scale to multiple backend replicas, this will need to move to a leader-elected worker or external queue. Out of scope here.
- Crash safety note: a process killed mid-dispatch (after send, before persist) will re-send the reminder on next startup. Acceptable for v1; can be tightened with a transactional pattern in the SQLite migration spec.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "3.2", "4.2", "4.3", "7.1"] },
    { "id": 3, "tasks": ["3.1", "4.4", "7.2"] },
    { "id": 4, "tasks": ["3.3", "3.4", "5.1", "7.3"] },
    { "id": 5, "tasks": ["5.2", "7.4"] },
    { "id": 6, "tasks": ["6", "8"] },
    { "id": 7, "tasks": ["9.1", "9.2", "9.3"] },
    { "id": 8, "tasks": ["10"] }
  ]
}
```
