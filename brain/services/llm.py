"""Ollama-backed language model service for RobotOS conversations."""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class LLMError(RuntimeError):
    """Raised when Ollama is unavailable or returns an invalid response."""


@dataclass(frozen=True, slots=True)
class LLMResult:
    """A completed language-model response."""

    text: str
    model: str


DEFAULT_SYSTEM_PROMPT = (
    "Είσαι το RobotOS, ένα φιλικό ρομπότ-βοηθός. "
    "Απαντάς αποκλειστικά στα ελληνικά, σύντομα, καθαρά και ευγενικά. "
    "Οι απαντήσεις σου θα εκφωνούνται, επομένως απόφυγε markdown, λίστες, "
    "emoji και περιττές επαναλήψεις."
)


class LLMService:
    """Generate concise Greek replies through Ollama's local HTTP API."""

    def __init__(
        self,
        model: str = "robot-greek",
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 120.0,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        urlopen: Any | None = None,
        num_predict: int = 80,
        num_ctx: int = 4096,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.system_prompt = system_prompt
        self._urlopen = urlopen or urllib.request.urlopen
        self.num_predict = num_predict
        self.num_ctx = num_ctx

    def _generate_sync(
        self,
        prompt: str,
        history: list[dict[str, str]] | None = None,
    ) -> LLMResult:
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise LLMError("Δεν υπάρχει κείμενο για αποστολή στο Ollama.")

        messages: list[dict[str, str]] = [
            {"role": "system", "content": self.system_prompt}
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": clean_prompt})

        body = json.dumps(
            {
                "model": self.model,
                "stream": False,
                "think": False,
                "messages": messages,
                "options": {"temperature": 0.2, "num_predict": self.num_predict, "num_ctx": self.num_ctx},
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with self._urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise LLMError(
                f"Το Ollama επέστρεψε HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise LLMError(
                "Δεν είναι δυνατή η σύνδεση με το Ollama. "
                "Βεβαιώσου ότι η υπηρεσία Ollama εκτελείται."
            ) from exc
        except (TimeoutError, OSError) as exc:
            raise LLMError(f"Η επικοινωνία με το Ollama απέτυχε: {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LLMError("Το Ollama επέστρεψε μη έγκυρη απάντηση JSON.") from exc

        try:
            text = str(payload["message"]["content"]).strip()
        except (KeyError, TypeError) as exc:
            raise LLMError("Η απάντηση του Ollama δεν περιέχει κείμενο.") from exc
        if not text:
            raise LLMError("Το Ollama επέστρεψε κενή απάντηση.")
        return LLMResult(text=text, model=str(payload.get("model", self.model)))

    async def generate(
        self,
        prompt: str,
        history: list[dict[str, str]] | None = None,
    ) -> LLMResult:
        """Generate a reply with optional short-term history."""

        return await asyncio.to_thread(self._generate_sync, prompt, history)
