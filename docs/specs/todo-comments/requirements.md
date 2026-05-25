# Requirements Document

## Introduction

Adds threaded comments to todos, with @mentions and image/file attachments. Each comment is owned by the user who created it, can be edited or deleted by its author, and can be a reply to a parent comment. Mentions reference users by username; in the current single-user scope they self-resolve, but the resolution and rendering pipeline is built so that future folder-sharing requires no schema change. Attachments reuse the existing image upload pattern used by todos.

This spec extends the existing `fullstack-todo-app` spec; all auth, ownership, validation, and persistence guarantees from that spec continue to apply.

## Glossary

- **Comment**: A user-authored message attached to a Todo. Has a unique id, author user_id, body, optional parent_comment_id (for replies), optional attachments[], created_at, and updated_at.
- **Thread**: A Comment together with its descendants (replies, replies-to-replies, etc.) reachable through `parent_comment_id`.
- **Mention**: A token of the form `@username` inside a comment body that resolves to an existing User at render time.
- **Attachment**: A file (currently images: png, jpg, jpeg, gif, webp) uploaded to a comment, stored in `/backend/data/uploads/`, referenced by a server-relative URL.
- **CommentService**: Service responsible for CRUD on comments, validating mentions, and managing attachments.
- **MAX_THREAD_DEPTH**: 5 (replies cannot nest more than 5 levels deep).
- **MAX_BODY_LENGTH**: 2000 characters.
- **MAX_ATTACHMENTS_PER_COMMENT**: 4.
- **MAX_ATTACHMENT_BYTES**: 5 MB per file.
- **ALLOWED_ATTACHMENT_MIME_TYPES**: image/png, image/jpeg, image/gif, image/webp.

## Requirements

### Requirement 1: Comment data model

**User Story:** As an authenticated user, I want each todo to optionally carry a list of comments, so that I can record context, follow-up notes, and discussions about that todo.

#### Acceptance Criteria

1. THE Todo model SHALL include a field `comments` whose value is an array of Comment objects, defaulting to `[]` when no comments exist.
2. THE Comment model SHALL include the fields: `id` (UUID4 string), `todo_id` (string referencing Todo.id), `author_id` (string referencing User.id), `body` (string), `parent_comment_id` (string or null), `mentions` (array of User.id strings), `attachments` (array of Attachment objects), `created_at` (ISO 8601 datetime), `updated_at` (ISO 8601 datetime or null).
3. THE Attachment model SHALL include the fields: `id` (UUID4 string), `url` (server-relative URL string), `filename` (original filename string), `mime_type` (string), `size_bytes` (integer).
4. WHEN a Todo is read from `todos.json` and does not contain a `comments` key, THE Backend SHALL treat `comments` as `[]`.
5. THE addition of the `comments` field SHALL NOT alter the validation, defaults, or behavior of any other Todo field.

### Requirement 2: Creating a top-level comment

**User Story:** As an authenticated user, I want to add a comment to one of my todos, so that I can record notes about it.

#### Acceptance Criteria

1. WHEN a `POST /api/todos/{id}/comments` request is received with a valid body, THE CommentService SHALL append a new Comment to the Todo identified by `id` and return the created Comment with HTTP 201.
2. WHEN a comment is created, THE CommentService SHALL set `id` to a fresh UUID4, `author_id` to the authenticated user's id, `created_at` to the current timestamp, `updated_at` to null, `parent_comment_id` to null (for top-level), `mentions` to the resolved mention list, and `attachments` to the resolved attachment list.
3. IF the request targets a todo that does not exist or does not belong to the authenticated user, THEN THE CommentService SHALL return a 404 not found error and SHALL NOT create a comment.
4. IF the body is missing, an empty string, or contains only whitespace, THEN THE CommentService SHALL return a 422 validation error identifying `body` as the invalid field.
5. IF the body length exceeds MAX_BODY_LENGTH characters (counted by Unicode code points), THEN THE CommentService SHALL return a 422 validation error identifying `body` as too long.

### Requirement 3: Replying to a comment (threads)

**User Story:** As an authenticated user, I want to reply to an existing comment, so that I can carry on a thread of related notes.

#### Acceptance Criteria

1. WHEN a `POST /api/todos/{id}/comments` request includes a `parent_comment_id` that references an existing comment on the same Todo, THE CommentService SHALL create the new comment with `parent_comment_id` set to that value.
2. IF `parent_comment_id` references a comment that does not exist, belongs to a different Todo, or is `null` when treated as a string, THEN THE CommentService SHALL return a 422 validation error identifying `parent_comment_id` as invalid.
3. IF accepting the new reply would produce a thread depth greater than MAX_THREAD_DEPTH (where a top-level comment has depth 1 and each reply increments depth by 1), THEN THE CommentService SHALL return a 422 validation error indicating maximum reply depth was reached.
4. THE CommentService SHALL compute thread depth by following `parent_comment_id` links from the new comment toward a top-level ancestor; if any cycle is detected during this traversal, THE CommentService SHALL return a 500 internal server error and SHALL NOT create the comment.
5. WHEN comments are returned to the client, THE Backend SHALL return them in chronological `created_at` ascending order; THE Frontend is responsible for assembling the parent/child rendering.

### Requirement 4: Mentions

**User Story:** As an authenticated user, I want to reference another user with `@username` in a comment, so that the reference is recorded and rendered as a link to that user.

#### Acceptance Criteria

1. WHEN a comment is created or updated, THE CommentService SHALL extract `@<username>` tokens from `body` using a regex that matches `@` followed by 3-30 characters of `[A-Za-z0-9_]`, ignoring matches inside backtick-delimited code spans.
2. WHEN extracting mentions, THE CommentService SHALL resolve each `@username` to a User by username; if the username matches an existing User, THE CommentService SHALL include that User's id in the `mentions` array, deduplicating ids.
3. IF a `@username` token does not match any existing User, THEN THE CommentService SHALL leave the literal text in `body` unchanged and SHALL NOT include any id in `mentions` for it.
4. THE CommentService SHALL preserve the original `body` text exactly as submitted; mention resolution SHALL only populate the `mentions` array.
5. WHEN the Frontend renders a comment, THE Frontend SHALL replace each `@username` token whose resolved User id appears in `mentions` with a styled link to that user; unresolved `@username` tokens SHALL render as plain text.
6. THE CommentService SHALL only resolve mentions to Users who have allowed mentions (currently every User; the resolution path SHALL accept future per-user opt-out without schema migration of comments).

### Requirement 5: Attachments

**User Story:** As an authenticated user, I want to attach images to a comment, so that I can include screenshots and visual references.

#### Acceptance Criteria

1. WHEN a `POST /api/todos/{id}/comments/attachments` request is received with a `multipart/form-data` body containing a single file, THE CommentService SHALL store the file in `/backend/data/uploads/comments/` with a filename derived from a fresh UUID4 plus the original extension, and return an Attachment object with HTTP 201.
2. THE returned Attachment object SHALL include `id`, `url` (server-relative path under `/uploads/comments/`), `filename` (sanitized original name), `mime_type`, and `size_bytes`.
3. IF the uploaded file's MIME type is not in ALLOWED_ATTACHMENT_MIME_TYPES, THEN THE CommentService SHALL return a 422 validation error identifying the file as an unsupported type and SHALL NOT persist the file.
4. IF the uploaded file exceeds MAX_ATTACHMENT_BYTES, THEN THE CommentService SHALL return a 413 payload too large error and SHALL NOT persist the file.
5. WHEN a `POST /api/todos/{id}/comments` request includes an `attachment_ids` array referencing previously uploaded Attachments, THE CommentService SHALL include the corresponding Attachment objects in the new comment's `attachments` array.
6. IF an `attachment_ids` entry does not match any uploaded attachment owned by the authenticated user, THEN THE CommentService SHALL return a 422 validation error identifying the offending attachment id.
7. IF a comment is submitted with more than MAX_ATTACHMENTS_PER_COMMENT attachments, THEN THE CommentService SHALL return a 422 validation error indicating the maximum was exceeded.
8. WHEN a comment is deleted, THE CommentService SHALL delete the underlying attachment files from disk for attachments that are not referenced by any other comment.

### Requirement 6: Editing a comment

**User Story:** As an authenticated user, I want to edit a comment I authored, so that I can correct typos or update information.

#### Acceptance Criteria

1. WHEN a `PUT /api/todos/{id}/comments/{cid}` request is received from the comment's author with an updated `body` and/or `attachment_ids`, THE CommentService SHALL update the comment, re-resolve mentions, set `updated_at` to the current timestamp, and return the updated Comment.
2. IF the requesting user is not the comment's author, THEN THE CommentService SHALL return a 404 not found error (matching the existing not-owned-resource handling pattern) and SHALL NOT modify the comment.
3. IF the comment id does not exist on the specified Todo, THEN THE CommentService SHALL return a 404 not found error.
4. THE CommentService SHALL NOT permit changing `parent_comment_id`, `author_id`, `todo_id`, or `created_at` via edit; any such fields in the request SHALL be ignored.
5. THE same validation rules from Requirements 2.4, 2.5, 4, and 5 SHALL apply to edits.

### Requirement 7: Deleting a comment

**User Story:** As an authenticated user, I want to delete a comment I authored, so that I can remove notes I no longer want recorded.

#### Acceptance Criteria

1. WHEN a `DELETE /api/todos/{id}/comments/{cid}` request is received from the comment's author, THE CommentService SHALL remove the comment from the Todo and return HTTP 204.
2. IF the deleted comment has replies (other comments referencing it as `parent_comment_id`), THEN THE CommentService SHALL retain those replies but replace the deleted comment with a tombstone comment whose `body` is `"[deleted]"`, `author_id` is the original author's id, `mentions` and `attachments` are emptied, and `updated_at` is set to the deletion time.
3. IF the deleted comment has no replies, THEN THE CommentService SHALL remove the comment record entirely.
4. IF the requesting user is not the comment's author, THEN THE CommentService SHALL return a 404 not found error and SHALL NOT modify any data.

### Requirement 8: Listing comments

**User Story:** As an authenticated user, I want to retrieve all comments on one of my todos, so that I can read the discussion.

#### Acceptance Criteria

1. WHEN a `GET /api/todos/{id}/comments` request is received for a todo owned by the authenticated user, THE CommentService SHALL return the full list of comments for that todo in `created_at` ascending order.
2. IF the todo does not exist or is not owned by the authenticated user, THEN THE CommentService SHALL return a 404 not found error.
3. THE response SHALL include each comment's resolved `mentions` (as an array of `{id, username}` objects, denormalized for frontend rendering convenience).
4. THE response SHALL omit comments that have been hard-deleted (per 7.4) and SHALL include tombstone comments (per 7.2).

### Requirement 9: Frontend rendering and authoring

**User Story:** As an authenticated user, I want to read and write comments inside the todo edit modal, so that I can manage them in context.

#### Acceptance Criteria

1. WHEN the user opens the todo edit modal, THE Frontend SHALL display all comments under a "Comments" section, rendered as a tree based on `parent_comment_id`.
2. THE Frontend SHALL display each comment with: author username, relative time of `created_at`, body (with mentions styled as links and attachments rendered inline as images), an edit button (visible only to the author), a delete button (visible only to the author), and a reply button.
3. WHEN the user clicks reply on a comment whose depth is less than MAX_THREAD_DEPTH, THE Frontend SHALL show a reply input scoped to that comment.
4. WHEN the user types `@` followed by characters in the comment input, THE Frontend SHALL show an autocomplete list of matching usernames and SHALL insert the selected `@username` token into the input.
5. WHEN the user attaches a file via drag-and-drop or file picker, THE Frontend SHALL upload it via the attachment endpoint, show a preview thumbnail with a remove control, and include the resulting attachment id in the next comment submit.
6. IF an upload exceeds size or type limits, THEN THE Frontend SHALL display a toast with the server's error message and SHALL NOT include the failed upload in the submission.
7. WHEN a comment operation (create, edit, delete) succeeds, THE Frontend SHALL update the comments list optimistically and refresh from the server in the background; on failure, THE Frontend SHALL revert the optimistic change and display an error toast.

### Requirement 10: Persistence and integrity

**User Story:** As a user, I want comments to be stored reliably alongside their todo, so that I do not lose them.

#### Acceptance Criteria

1. THE JSON_Store SHALL persist comments inline within the parent Todo's record in `todos.json` (no separate file).
2. FOR ALL valid Comment objects, serializing the parent Todo to JSON and deserializing back SHALL produce an equivalent Todo whose `comments` array is element-wise equal to the original (round-trip property).
3. THE atomic-write guarantee from `fullstack-todo-app` Requirement 14.8 SHALL apply unchanged when comments are added, edited, or deleted.
4. THE existing user-isolation guarantees (`fullstack-todo-app` Requirement 9, Property 9) SHALL apply to comments: a user SHALL only be able to read, create, edit, or delete comments on todos they own.
