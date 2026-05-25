"""Email service for reminder dispatch.

Two interchangeable backends:
    - ``SmtpBackend``: real outbound delivery via ``smtplib``, wrapped in
      ``asyncio.to_thread`` so it never blocks the event loop.
    - ``FileLogBackend``: append-one-JSON-per-line to ``data/email_log.jsonl``.
      Never raises — used as the local-dev fallback when SMTP env vars are
      missing.

``build_email_service(env)`` picks one based on the presence of SMTP_* env
vars. The chosen backend is logged once at startup.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Mapping, Protocol

log = logging.getLogger(__name__)

REQUIRED_SMTP_VARS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM")


class EmailBackend(Protocol):
    """Pluggable email delivery backend."""

    async def send(
        self, *, to: str, subject: str, text: str, html: str
    ) -> None: ...


class SmtpBackend:
    """Sends via :mod:`smtplib`, wrapping the blocking calls in a thread."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        user: str,
        password: str,
        sender: str,
        use_tls: str = "ssl",
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.sender = sender
        self.use_tls = use_tls

    async def send(self, *, to: str, subject: str, text: str, html: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.sender
        message["To"] = to
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        await asyncio.to_thread(self._send_sync, message)

    def _send_sync(self, message: EmailMessage) -> None:
        if self.use_tls == "starttls":
            with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
                smtp.starttls()
                smtp.login(self.user, self.password)
                smtp.send_message(message)
        elif self.use_tls == "none":
            with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
                smtp.login(self.user, self.password)
                smtp.send_message(message)
        else:  # default: SSL
            with smtplib.SMTP_SSL(self.host, self.port, timeout=30) as smtp:
                smtp.login(self.user, self.password)
                smtp.send_message(message)


class FileLogBackend:
    """Appends one JSON line per email to a log file. Never raises."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def send(
        self, *, to: str, subject: str, text: str, html: str
    ) -> None:
        try:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "to": to,
                "subject": subject,
                "text_body": text,
                "html_body": html,
            }
            await asyncio.to_thread(self._append, entry)
        except Exception:  # pragma: no cover - swallow per contract
            log.exception("FileLogBackend write failed")

    def _append(self, entry: dict) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


class InMemoryBackend:
    """Test helper: records every send call. Optionally fails N times first."""

    def __init__(self, *, fail_first: int = 0):
        self.sent: list[dict] = []
        self._remaining_failures = fail_first

    async def send(
        self, *, to: str, subject: str, text: str, html: str
    ) -> None:
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("simulated SMTP failure")
        self.sent.append(
            {"to": to, "subject": subject, "text": text, "html": html}
        )


class EmailService:
    """Builds reminder emails and dispatches via the configured backend."""

    def __init__(self, backend: EmailBackend, frontend_url: str):
        self.backend = backend
        self.frontend_url = frontend_url.rstrip("/")

    async def send_reminder(self, *, user_email: str, todo: dict) -> None:
        subject, text, html_body = self.render(todo, self.frontend_url)
        await self.backend.send(
            to=user_email, subject=subject, text=text, html=html_body
        )

    @staticmethod
    def render(todo: dict, frontend_url: str) -> tuple[str, str, str]:
        title = (todo.get("title") or "").strip() or "(no title)"
        subject = f"Reminder: {title}"
        if len(subject) > 80:
            subject = subject[:77] + "..."

        due_date = todo.get("due_date") or "No due date"
        priority = todo.get("priority") or "medium"
        reminder_at = todo.get("reminder_at") or ""
        dash_url = f"{frontend_url}/dashboard"

        text = (
            f"Reminder for: {title}\n"
            f"Due: {due_date}\n"
            f"Priority: {priority}\n"
            f"Reminder time (UTC): {reminder_at}\n\n"
            f"Open the dashboard: {dash_url}\n"
        )

        # HTML body: escape every piece of user-supplied text.
        safe_title = html.escape(title)
        safe_due = html.escape(str(due_date))
        safe_priority = html.escape(str(priority))
        safe_reminder = html.escape(str(reminder_at))
        safe_desc = html.escape(str(todo.get("description") or ""))
        desc_block = (
            f"<p style='color:#475569;'>{safe_desc}</p>" if safe_desc else ""
        )

        html_body = (
            "<div style=\"font-family:system-ui,sans-serif;max-width:560px;"
            "padding:24px;\">"
            f"<h2 style='color:#1e293b;'>Reminder: {safe_title}</h2>"
            f"{desc_block}"
            "<ul style='line-height:1.6;color:#334155;'>"
            f"<li><b>Due:</b> {safe_due}</li>"
            f"<li><b>Priority:</b> {safe_priority}</li>"
            f"<li><b>Reminder (UTC):</b> {safe_reminder}</li>"
            "</ul>"
            f"<p><a href='{html.escape(dash_url)}' "
            "style='background:#6366f1;color:white;padding:10px 16px;"
            "border-radius:6px;text-decoration:none;'>Open dashboard</a></p>"
            "</div>"
        )
        return subject, text, html_body


def _mask_host(host: str) -> str:
    if not host or "." not in host:
        return host
    head, _, tail = host.partition(".")
    masked_head = head[:1] + "*" * max(0, len(head) - 1)
    return f"{masked_head}.{tail}"


def build_email_service(
    env: Mapping[str, str], *, default_log_path: Path | None = None
) -> EmailService:
    """Auto-select the backend based on env vars; log the choice once."""
    if all(env.get(k) for k in REQUIRED_SMTP_VARS):
        backend: EmailBackend = SmtpBackend(
            host=env["SMTP_HOST"],
            port=int(env["SMTP_PORT"]),
            user=env["SMTP_USER"],
            password=env["SMTP_PASS"],
            sender=env["SMTP_FROM"],
            use_tls=env.get("SMTP_USE_TLS", "ssl"),
        )
        log.info(
            "EmailService backend=smtp host=%s", _mask_host(env["SMTP_HOST"])
        )
    else:
        path = default_log_path or Path("data/email_log.jsonl")
        backend = FileLogBackend(path)
        log.info("EmailService backend=file-log path=%s", path)
    return EmailService(
        backend=backend,
        frontend_url=env.get("FRONTEND_URL", "http://localhost:3000"),
    )
