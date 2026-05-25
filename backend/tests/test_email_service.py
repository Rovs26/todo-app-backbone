"""Unit tests for EmailService rendering + backend selection."""

import asyncio
import json
from pathlib import Path

import pytest

from services.email_service import (
    EmailService,
    FileLogBackend,
    InMemoryBackend,
    SmtpBackend,
    build_email_service,
)


# --- _render -----------------------------------------------------------------


def test_subject_starts_with_reminder_prefix():
    todo = {"title": "Pay rent"}
    subject, _, _ = EmailService.render(todo, "http://app")
    assert subject == "Reminder: Pay rent"


def test_subject_is_truncated_to_80_chars():
    todo = {"title": "x" * 200}
    subject, _, _ = EmailService.render(todo, "http://app")
    assert len(subject) == 80
    assert subject.endswith("...")


def test_html_body_escapes_user_text_property_8():
    todo = {
        "title": "<script>alert('xss')</script>",
        "description": "1 < 2 & ok",
    }
    _, _, html_body = EmailService.render(todo, "http://app")
    assert "<script>" not in html_body
    assert "&lt;script&gt;" in html_body
    assert "1 &lt; 2 &amp; ok" in html_body


def test_text_body_includes_dashboard_link():
    todo = {"title": "x"}
    _, text, _ = EmailService.render(todo, "https://app.example.com")
    assert "https://app.example.com/dashboard" in text


def test_text_body_includes_no_due_date_fallback():
    todo = {"title": "x", "due_date": None}
    _, text, _ = EmailService.render(todo, "http://app")
    assert "No due date" in text


# --- build_email_service -----------------------------------------------------


def test_build_uses_smtp_when_all_env_present_property_9(tmp_path):
    env = {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "465",
        "SMTP_USER": "u",
        "SMTP_PASS": "p",
        "SMTP_FROM": "noreply@example.com",
    }
    svc = build_email_service(env, default_log_path=tmp_path / "log.jsonl")
    assert isinstance(svc.backend, SmtpBackend)


def test_build_uses_filelog_when_smtp_env_missing_property_9(tmp_path):
    env = {"SMTP_HOST": "smtp.example.com"}  # incomplete
    svc = build_email_service(env, default_log_path=tmp_path / "log.jsonl")
    assert isinstance(svc.backend, FileLogBackend)


def test_build_uses_filelog_when_one_var_is_empty_string(tmp_path):
    env = {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "465",
        "SMTP_USER": "",  # empty counts as missing
        "SMTP_PASS": "p",
        "SMTP_FROM": "noreply@example.com",
    }
    svc = build_email_service(env, default_log_path=tmp_path / "log.jsonl")
    assert isinstance(svc.backend, FileLogBackend)


# --- FileLogBackend ----------------------------------------------------------


def test_file_log_backend_appends_one_line_per_send(tmp_path):
    path = tmp_path / "email_log.jsonl"
    backend = FileLogBackend(path)
    asyncio.run(
        backend.send(to="a@x", subject="hi", text="text", html="<p>html</p>")
    )
    asyncio.run(
        backend.send(to="b@x", subject="hi2", text="t2", html="<p>h2</p>")
    )
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 2
    rec = json.loads(lines[0])
    assert rec["to"] == "a@x"
    assert rec["subject"] == "hi"


# --- InMemoryBackend (test helper sanity check) ------------------------------


def test_in_memory_backend_fails_first_then_succeeds():
    backend = InMemoryBackend(fail_first=2)
    with pytest.raises(RuntimeError):
        asyncio.run(backend.send(to="a", subject="s", text="t", html="h"))
    with pytest.raises(RuntimeError):
        asyncio.run(backend.send(to="a", subject="s", text="t", html="h"))
    asyncio.run(backend.send(to="a", subject="s", text="t", html="h"))
    assert len(backend.sent) == 1
