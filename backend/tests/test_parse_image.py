"""Unit tests for ai_service.parse_image with a mocked OpenAI client."""

import json
from types import SimpleNamespace

import pytest

from services import ai_service


class _FakeClient:
    def __init__(self, *, content: str = "", raise_exc: Exception | None = None):
        self._content = content
        self._raise = raise_exc
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._raise is not None:
            raise self._raise
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._content))]
        )


def _patch_client(monkeypatch, client):
    monkeypatch.setattr(ai_service, "_client", lambda: client)


def test_parse_image_returns_cleaned_items(monkeypatch):
    payload = json.dumps(
        {
            "items": [
                {"title": "Buy milk", "priority": "high", "tags": ["Shopping"]},
                {"title": "  Pay rent  ", "due_date": "2026-06-01"},
                {"title": "", "priority": "low"},  # filtered (empty title)
                {"title": "x", "priority": "weird"},  # priority dropped
            ]
        }
    )
    _patch_client(monkeypatch, _FakeClient(content=payload))

    out = ai_service.parse_image(b"\x89PNG fakebytes", "image/png")
    assert out == {
        "items": [
            {"title": "Buy milk", "priority": "high", "tags": ["shopping"]},
            {"title": "Pay rent", "due_date": "2026-06-01"},
            {"title": "x"},
        ]
    }


def test_parse_image_truncates_to_30_items(monkeypatch):
    payload = json.dumps({"items": [{"title": f"Task {i}"} for i in range(50)]})
    _patch_client(monkeypatch, _FakeClient(content=payload))

    out = ai_service.parse_image(b"x", "image/jpeg")
    assert len(out["items"]) == 30
    assert out["items"][-1]["title"] == "Task 29"


def test_parse_image_raises_on_api_error(monkeypatch):
    _patch_client(monkeypatch, _FakeClient(raise_exc=RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        ai_service.parse_image(b"x", "image/png")


def test_parse_image_raises_on_unavailable(monkeypatch):
    monkeypatch.setattr(ai_service, "_client", lambda: None)
    with pytest.raises(RuntimeError, match="ai_unavailable"):
        ai_service.parse_image(b"x", "image/png")


def test_parse_image_raises_on_bad_json(monkeypatch):
    _patch_client(monkeypatch, _FakeClient(content="not json"))
    with pytest.raises(RuntimeError, match="JSONDecodeError"):
        ai_service.parse_image(b"x", "image/png")


def test_parse_image_handles_missing_items_field(monkeypatch):
    _patch_client(monkeypatch, _FakeClient(content="{}"))
    out = ai_service.parse_image(b"x", "image/png")
    assert out == {"items": []}
