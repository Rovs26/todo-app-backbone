# Spec: Natural-language Quick Add

Combined requirements + design + tasks. Extends `fullstack-todo-app`. Optional integration points with `recurring-todos`.

## Goal

A single-line input at the top of the dashboard. Type "pay rent every 1st of the month, high priority" → AI parses it into a structured todo and opens the create modal pre-populated for the user to review/edit/confirm.

## Requirements

### Requirement 1: Parse endpoint

#### Acceptance Criteria
1. WHEN `POST /api/ai/parse-todo` is received from an authenticated user with body `{ text: string }`, THE AI_Service SHALL call OpenAI with a JSON-schema-constrained response and return `{ title, description?, priority?, due_date?, reminder_at?, recurrence?, tags?, folder_id?, subtasks? }`.
2. THE AI_Service SHALL use `gpt-4o-mini` with `response_format={"type":"json_schema", ...}` so the model is forced to return valid shape.
3. THE prompt SHALL include the current date (UTC) so relative phrases like "tomorrow" resolve correctly.
4. THE prompt SHALL receive a list of the user's folders (id + name) so the model can pick a `folder_id` if the user names one.
5. IF the OpenAI key is missing, THEN THE endpoint SHALL fall back to a deterministic local parser (see Design) and return `summary_source: "local"` so the frontend can warn.
6. IF the OpenAI call fails (network, rate limit), THEN THE endpoint SHALL return 503 with the raw error class and a hint to retry; the frontend SHALL surface the error as a toast.
7. THE endpoint SHALL accept `text` up to 500 characters; longer requests SHALL return 422.

### Requirement 2: Local fallback parser

#### Acceptance Criteria
1. THE local parser SHALL extract:
    - `!high`, `!med`, `!low` → priority
    - `#tag` → tags (multiple)
    - `@YYYY-MM-DD` → due_date
    - `every day|week|month|year` → recurrence
    - Remaining text → title (trimmed)
2. THE local parser SHALL never raise; on any input it SHALL return at minimum `{ title: <text> }`.

### Requirement 3: Frontend quick-add bar

#### Acceptance Criteria
1. THE dashboard SHALL render a single input at the top of the todo list area with placeholder text "Type a task… (e.g. 'pay rent next Friday !high #bills')".
2. WHEN the user presses Enter, THE Frontend SHALL call `POST /api/ai/parse-todo`, await the response, and open the existing create modal pre-populated with the parsed fields.
3. WHEN the call is in flight, THE Frontend SHALL show a loading spinner inside the input.
4. WHEN the parser returns `summary_source: "local"`, THE Frontend SHALL show a small "(parsed locally — no AI key)" tooltip on the modal.
5. THE Frontend SHALL never silent-create the todo. The user always reviews and confirms.

## Design

- New `routers/ai.py` route `POST /parse-todo` (the `ai` router already exists).
- New `ai_service.parse_todo(text, user, folders) -> ParsedTodo`.
- Schema enforcement via OpenAI `response_format={"type":"json_schema", "json_schema": {...}}`.
- Local fallback in `services/quick_add_parser.py` — pure function, easy to test.
- Frontend: `components/QuickAddBar.vue` mounted at the top of the dashboard list pane, calls `aiApi.parseTodo(text)`.
- Existing `TodoForm.vue` modal accepts a `prefill: Partial<TodoCreate>` prop (already does for editing; reuse the same path with `id: null`).

## Tasks

- [ ] 1. Backend
  - [ ] 1.1 Add `ParsedTodo` to `models.py`
  - [ ] 1.2 Implement `services/quick_add_parser.py:parse_local(text)` (pure)
  - [ ] 1.3 Add `ai_service.parse_todo(text, folders) -> dict`; OpenAI call with JSON-schema response_format
  - [ ] 1.4 Add `POST /api/ai/parse-todo` to `routers/ai.py`
  - [ ]* 1.5 Pytest for `parse_local`: priority/tag/date/recurrence extraction + fallback to title-only

- [ ] 2. Frontend
  - [ ] 2.1 Add `aiApi.parseTodo(text)` to `utils/api.ts`
  - [ ] 2.2 Create `components/QuickAddBar.vue`
  - [ ] 2.3 Mount it at the top of the dashboard list pane; on parse success, emit `prefill` to the create modal and open it
  - [ ] 2.4 Toast on error; loading spinner during request

- [ ] 3. Verification
  - [ ] 3.1 pytest passes; manual: type "buy bread tomorrow !high #shopping" → modal opens with title, due_date, priority=high, tag=shopping
  - [ ] 3.2 Disable OpenAI key temporarily → confirm local fallback works
