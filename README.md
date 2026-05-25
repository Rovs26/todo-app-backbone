# Full-Stack Todo Application

A full-stack Todo application with user authentication, full CRUD operations, filtering/sorting, and a responsive dashboard UI.

- **Backend**: Python FastAPI with SQLite (via SQLAlchemy) and JWT authentication
- **Frontend**: Nuxt 3 with TailwindCSS and Pinia state management

## Prerequisites

- **Python** 3.11 or higher
- **Node.js** 18 or higher
- **npm** (comes with Node.js)

## Backend Setup

```cmd
cd backend

# Create and activate a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the backend server
uvicorn main:app --reload
```

The backend API runs at **http://localhost:8000**.

## Frontend Setup

```cmd
cd frontend

# Install dependencies
npm install

# Start the frontend dev server
npm run dev
```

The frontend runs at **http://localhost:3000**.

## Running Both Servers

You can start both servers at once using the provided script:

**Windows:**
```cmd
run.bat
```

**Linux/macOS:**
```bash
chmod +x run.sh
./run.sh
```

This opens separate terminal windows for the backend and frontend servers.

## Project Structure

```
todo-app/
├── backend/
│   ├── main.py              # FastAPI application entry point
│   ├── models.py            # Pydantic data models
│   ├── store.py             # JSONStore (deprecated) + SQLStore adapter
│   ├── db.py                # SQLAlchemy engine + session factory
│   ├── db_models.py         # ORM row models (one per table)
│   ├── dependencies.py      # Shared engine + Auth dependency (JWT extraction)
│   ├── exceptions.py        # Custom exception classes and handlers
│   ├── requirements.txt     # Python dependencies
│   ├── scripts/             # One-shot migration + rollback scripts
│   ├── data/                # Runtime data (app.db SQLite file + JSON backups)
│   ├── routers/             # API route handlers
│   │   ├── auth.py          # Auth endpoints (/api/auth/*)
│   │   └── todos.py         # Todo endpoints (/api/todos/*)
│   └── services/            # Business logic
│       ├── auth_service.py  # Authentication service
│       └── todo_service.py  # Todo CRUD service
├── frontend/
│   ├── pages/               # Nuxt pages (login, register, dashboard)
│   ├── components/          # Vue components
│   ├── composables/         # Composable functions
│   ├── stores/              # Pinia stores (auth, todos)
│   ├── middleware/          # Route guards
│   ├── nuxt.config.ts       # Nuxt configuration
│   └── package.json         # Node.js dependencies
├── README.md
├── run.bat                  # Windows script to start both servers
└── run.sh                   # Linux/macOS script to start both servers
```

## Data layer (SQLite)

The backend persists to a single SQLite database at `backend/data/app.db`.
Schema is created at app startup via `init_db()` (idempotent — safe to run
on every boot). Each table corresponds to a former JSON file:
`users`, `folders`, `todos`, `notifications`, `attachments`, `reminder_send_log`.

Migrate existing `data/*.json` files into SQLite (idempotent; backs up
sources as `*.json.bak` first):

```bash
cd backend
python3 -m scripts.migrate_json_to_sqlite          # full run
python3 -m scripts.migrate_json_to_sqlite --dry-run
```

One-step rollback exports SQLite tables back to JSON files:

```bash
python3 -m scripts.rollback_sqlite_to_json
```

Services interact with the DB via the `SQLStore` adapter (same surface as
the legacy `JSONStore`), so routers, the reminder scheduler, and existing
tests need no signature changes. List-typed fields (tags, subtasks,
comments) are stored as JSON-text columns; scalar fields are real columns
with indexes on `user_id`, `folder_id`, `status`, and `email`.

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Log in with email/username and password |
| POST | `/api/auth/logout` | Log out (clears cookie) |
| GET | `/api/auth/me` | Get current user info |
| PUT | `/api/auth/me` | Update user preferences (e.g. `email_reminders_enabled`) |

### Email reminders (environment variables)

The reminder scheduler runs in-process and polls `todos.json` every 60s for
todos whose `reminder_at` has passed. If `SMTP_*` is fully configured it uses
SMTP; otherwise it appends to `backend/data/email_log.jsonl` (dev mode).

| Variable | Default | Description |
|---|---|---|
| `SMTP_HOST` | _(empty)_ | SMTP server host |
| `SMTP_PORT` | _(empty)_ | SMTP server port (465 for SSL, 587 for STARTTLS) |
| `SMTP_USER` | _(empty)_ | SMTP username |
| `SMTP_PASS` | _(empty)_ | SMTP password |
| `SMTP_FROM` | _(empty)_ | From address used in outgoing reminders |
| `SMTP_MODE` | `ssl` | `ssl`, `starttls`, or `none` |
| `REMINDER_RATE_LIMIT_PER_MINUTE` | `100` | Max reminders dispatched per rolling 60s window |
| `FRONTEND_URL` | `http://localhost:3000` | Link target embedded in the email body |

If any of `SMTP_HOST/PORT/USER/PASS/FROM` is missing or empty the service
falls back to the file-log backend (no emails are sent).

### Todos

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/todos` | List todos (supports `status`, `priority`, `sort_by` query params) |
| POST | `/api/todos` | Create a new todo |
| GET | `/api/todos/{id}` | Get a specific todo |
| PUT | `/api/todos/{id}` | Update a todo |
| DELETE | `/api/todos/{id}` | Delete a todo |

### AI

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ai/status` | Returns `{enabled}` based on `OPENAI_API_KEY` |
| POST | `/api/ai/parse-todo` | Parse a NL phrase into `{data, source}` for the quick-add bar |
| POST | `/api/ai/parse-image` | Extract todo candidates from a photo (multipart image) |
| POST | `/api/ai/transcribe` | Whisper transcription (multipart audio) |
| POST | `/api/ai/voice-action` | Plan structured actions from a transcript (no mutations) |
| POST | `/api/ai/voice-action/apply` | Execute a user-approved action list in order |
| POST | `/api/ai/chat` | Conversational assistant grounded in the user's todos |
