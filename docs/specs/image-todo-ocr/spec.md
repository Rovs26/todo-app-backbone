# Spec: Image OCR / Describe → Todos

Combined requirements + design + tasks. Extends `fullstack-todo-app`.

## Goal

Snap a photo of a whiteboard or handwritten list. AI extracts each line item and proposes a batch of todos. User picks which to actually create.

## Requirements

### Requirement 1: Parse-image endpoint

#### Acceptance Criteria
1. WHEN `POST /api/ai/parse-image` is received with multipart `file` from an authenticated user, THE AI_Service SHALL send the image bytes to GPT-4o (vision) with a JSON-schema response asking for a list of `{ title, priority?, due_date?, tags? }` objects.
2. THE response SHALL be `{ items: ParsedTodo[], image_url: string }` where `image_url` is the saved upload path (so the frontend can show what the user uploaded).
3. THE endpoint SHALL accept images of MIME type `image/png`, `image/jpeg`, `image/jpg`, `image/webp`, `image/gif`, up to 8 MB.
4. THE endpoint SHALL store the upload under `data/uploads/ocr/<uuid>.<ext>` and serve it via the existing `/uploads` static mount.
5. IF the OpenAI key is missing, THEN THE endpoint SHALL return 503 with a message that vision OCR requires an API key (no local fallback — vision is non-trivial without a model).
6. IF the OpenAI call fails or returns an unparseable response, THEN THE endpoint SHALL return 502 with the error class; the frontend SHALL toast.
7. THE endpoint SHALL truncate the `items` list to 30 entries (defence against runaway responses).

### Requirement 2: Frontend batch preview

#### Acceptance Criteria
1. THE dashboard SHALL render a 📷 button next to the quick-add bar.
2. Clicking the button SHALL open a small dialog with a file picker and a drag-drop zone.
3. WHEN a file is selected, THE Frontend SHALL upload it, await the response, and render the proposed items in a checklist (each row: checkbox, editable title, priority pill, optional date).
4. THE user SHALL be able to: toggle each row on/off, edit titles inline, set/clear the active folder for the whole batch.
5. WHEN the user clicks "Create N todos", THE Frontend SHALL issue one `POST /api/todos` per selected row in parallel (Promise.all) and close the dialog on success.
6. IF any individual create fails, THE Frontend SHALL keep the dialog open with the failed rows still selected and a toast indicating the failure count.

## Design

- New endpoint in `routers/ai.py`: `POST /parse-image`.
- New `ai_service.parse_image(image_bytes, mime)` builds the OpenAI request with `vision` content type, schema-constrained response.
- Upload helper reuses the existing image-upload pattern from `routers/todos.py:upload_image`.
- New `components/ImageImportDialog.vue`. Reuses existing toast + folder dropdown.

## Tasks

- [ ] 1. Backend
  - [ ] 1.1 Add `ParsedTodo` (shared with nlp-quick-add) and `ParsedImageResponse` to `models.py`
  - [ ] 1.2 Implement `ai_service.parse_image(bytes, mime, model='gpt-4o') -> list[ParsedTodo]`
  - [ ] 1.3 Add `POST /api/ai/parse-image` to `routers/ai.py` with file upload handling
  - [ ] 1.4 Ensure `data/uploads/ocr/` exists and is gitignored
  - [ ]* 1.5 Pytest with mocked OpenAI client returning canned JSON

- [ ] 2. Frontend
  - [ ] 2.1 Add `aiApi.parseImage(file)` to `utils/api.ts`
  - [ ] 2.2 Create `components/ImageImportDialog.vue`
  - [ ] 2.3 Wire the 📷 button into the dashboard quick-add area
  - [ ] 2.4 Parallel-create implementation in the dialog

- [ ] 3. Verification
  - [ ] 3.1 Upload a screenshot of a list → dialog shows extracted items → create selected → todos appear
