# Spec: Voice Agent (Plan + Confirm)

Combined requirements + design + tasks. Extends `fullstack-todo-app`, `todo-comments`, `recurring-todos`.

## Goal

Hold a 🎙️ Voice button, speak freely, AI plans actions (create folders, todos, comments), shows a confirmation panel, applies on user approval.

## Requirements

### Requirement 1: Voice-action endpoint

#### Acceptance Criteria
1. WHEN `POST /api/ai/voice-action` is received with body `{ transcript: string, context?: { active_folder_id?: string, active_todo_id?: string } }`, THE AI_Service SHALL call OpenAI with the OpenAI tool-calling schema described in Design and return `{ actions: VoiceAction[], assistant_reply: string }`.
2. THE endpoint SHALL NOT mutate any user data. It only proposes a plan.
3. THE supported actions (tool schemas) SHALL be exactly: `create_folder(name, color?, icon?)`, `create_todo(title, folder_id?, folder_name?, priority?, due_date?, reminder_at?, recurrence?, tags?, subtasks?)`, `add_comment(todo_id?, todo_title?, body)`, `mark_done(todo_id?, todo_title?)`, `set_priority(todo_id?, todo_title?, priority)`.
4. THE endpoint SHALL receive the user's current folders and recent todos (top 20 by `updated_at`) so the model can resolve names to ids.
5. WHEN the model produces `folder_name` instead of `folder_id`, THE service SHALL resolve to an id by case-insensitive name match against the user's folders; if no match, THE service SHALL mark that action with `resolved_folder_id: null` and let the frontend show "Folder will be created".
6. WHEN the model produces `todo_title` instead of `todo_id` for add_comment/mark_done/set_priority, THE service SHALL resolve to an id via fuzzy match (substring, case-insensitive) against the user's recent todos; if multiple match, THE service SHALL pick the most recent.
7. THE actions list SHALL be capped at 20 entries.
8. IF the transcript is empty or > 2000 chars, THEN THE endpoint SHALL return 422.
9. IF the OpenAI call fails, THEN THE endpoint SHALL return 502 with the error class.

### Requirement 2: Apply endpoint

#### Acceptance Criteria
1. WHEN `POST /api/ai/voice-action/apply` is received with `{ actions: VoiceAction[] }` from an authenticated user, THE AI_Service SHALL execute each action in order against the existing service layer (FolderService, TodoService, CommentService).
2. THE service SHALL stop at the first failed action and return `{ applied: [...], failed: { index, action, error }, remaining: [...] }`.
3. WHEN a `create_todo` action references a folder by `folder_name` that does not exist, THE service SHALL first create the folder, capture its id, and inject it into the todo's `folder_id` before creating the todo (multi-step apply).
4. ALL actions SHALL be tagged with `source: "voice"` where the receiving service supports it (currently `comments` only; others store no source).

### Requirement 3: Frontend voice button + confirmation panel

#### Acceptance Criteria
1. THE dashboard header SHALL include a 🎙️ Voice button (distinct from the per-field mic that already exists).
2. WHEN held (push-to-talk) OR clicked-to-toggle, THE Frontend SHALL record audio via MediaRecorder.
3. WHEN recording stops, THE Frontend SHALL post audio to the existing `/api/ai/transcribe` (Whisper) and then post the resulting transcript to `/api/ai/voice-action`.
4. WHEN the response arrives, THE Frontend SHALL show a confirmation panel with: the transcript, the assistant's reply, and a list of proposed actions each rendered as a human-readable line ("Create folder 'School project'", "Create todo 'Buy bread' in folder 'Groceries'", "Add comment to 'Buy bread': ...").
5. EACH action row SHALL have a checkbox so the user can uncheck unwanted actions before applying.
6. THE panel SHALL have buttons: `Apply` (sends checked actions to `/voice-action/apply`), `Cancel`, `Edit transcript` (re-runs the planner with edited text).
7. WHEN apply completes, THE Frontend SHALL refresh todos and folders, toast a summary ("Applied N actions"), and close the panel.
8. IF apply partially fails, THE panel SHALL stay open showing applied items as ✓ and failed items as ✗ with the error.
9. THE 🎙️ button SHALL be disabled when `ai_status.enabled === false`.

## Design

```
Audio → MediaRecorder → /api/ai/transcribe (Whisper) → transcript
Transcript → /api/ai/voice-action (plan, no mutation) → [actions]
User reviews → /api/ai/voice-action/apply → mutations via existing services
```

OpenAI tool schema (sketch):

```jsonc
[
  { "type": "function", "function": { "name": "create_folder", "parameters": {...} }},
  { "type": "function", "function": { "name": "create_todo", "parameters": {...} }},
  { "type": "function", "function": { "name": "add_comment", "parameters": {...} }},
  { "type": "function", "function": { "name": "mark_done", "parameters": {...} }},
  { "type": "function", "function": { "name": "set_priority", "parameters": {...} }}
]
```

The planner uses `tool_choice: "auto"` and may emit multiple tool calls in a single response (parallel function calling).

Confirmation UI: a modal pinned to the bottom-right (above the chatbot widget), with each action as a list item bearing a checkbox.

## Tasks

- [ ] 1. Backend models + planner
  - [ ] 1.1 Add `VoiceAction` (discriminated union via Pydantic) and `VoiceActionResponse` to `models.py`
  - [ ] 1.2 Implement `ai_service.plan_voice_action(transcript, user, folders, todos) -> VoiceActionResponse`
  - [ ] 1.3 Add `POST /api/ai/voice-action` to `routers/ai.py`
  - [ ]* 1.4 Pytest with mocked OpenAI returning canned tool calls

- [ ] 2. Backend apply
  - [ ] 2.1 Implement `ai_service.apply_voice_actions(user, actions) -> ApplyResponse`
  - [ ] 2.2 Add `POST /api/ai/voice-action/apply` to `routers/ai.py`
  - [ ]* 2.3 Integration test: 3-action plan apply → folders+todos+comments created in order

- [ ] 3. Frontend voice button + confirmation
  - [ ] 3.1 Add `aiApi.voiceAction(transcript, context)` and `aiApi.applyVoiceActions(actions)` to `utils/api.ts`
  - [ ] 3.2 Create `composables/useVoiceAgent.ts` with state machine: idle → recording → transcribing → planning → reviewing → applying → done|error
  - [ ] 3.3 Create `components/VoiceAgentButton.vue` (header button)
  - [ ] 3.4 Create `components/VoiceAgentPanel.vue` (confirmation modal)
  - [ ] 3.5 Wire into dashboard header
  - [ ] 3.6 Refresh todos + folders on apply success

- [ ] 4. Verification
  - [ ] 4.1 Manual: hold mic, say "create a folder called school and add todos buy notebook, finish essay", confirm panel shows 3 actions, apply
  - [ ] 4.2 Manual partial failure: have one action reference a deleted todo → confirm panel shows ✗

## Notes

- This is the largest single spec. Plan ~2-3× any other.
- The "always confirm" UX is a deliberate safety choice. We do not silent-execute even low-risk actions; if you say "delete everything", you see it before it happens.
- Backend never accepts an apply call that wasn't planned via voice-action — we don't authenticate "plans" cryptographically; the apply endpoint runs whatever it's given through the standard user-scoped services, so the worst case is "user accidentally applies the action they accepted".
