"""Tests for the B1.7 Ollama language-model service."""

from __future__ import annotations

import asyncio
import json
import urllib.error
from typing import Any

import pytest

from brain.services.llm import LLMError, LLMService


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._data


def test_llm_service_calls_ollama_chat_api() -> None:
    captured: dict[str, Any] = {}

    def urlopen(request: Any, timeout: float) -> FakeResponse:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(
            {
                "model": "robot-greek",
                "message": {"role": "assistant", "content": "Γεια σου!"},
            }
        )

    service = LLMService(urlopen=urlopen, timeout_seconds=12)
    result = asyncio.run(service.generate("Γεια σου"))

    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["timeout"] == 12
    assert captured["body"]["model"] == "robot-greek"
    assert captured["body"]["messages"][-1]["content"] == "Γεια σου"
    assert result.text == "Γεια σου!"


def test_llm_service_reports_offline_ollama() -> None:
    def urlopen(request: Any, timeout: float) -> FakeResponse:
        raise urllib.error.URLError("connection refused")

    service = LLMService(urlopen=urlopen)

    with pytest.raises(LLMError, match="Ollama"):
        asyncio.run(service.generate("δοκιμή"))


def test_llm_service_rejects_empty_prompt() -> None:
    service = LLMService()

    with pytest.raises(LLMError, match="κείμενο"):
        asyncio.run(service.generate("   "))
