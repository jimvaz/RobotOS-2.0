"""Ollama-backed language model service for RobotOS conversations."""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from time import perf_counter
from typing import Any, AsyncIterator


class LLMError(RuntimeError):
    """Raised when Ollama is unavailable or returns an invalid response."""


@dataclass(frozen=True, slots=True)
class LLMResult:
    """A completed language-model response."""

    text: str
    model: str


class LLMStream:
    """Async text stream produced by Ollama's newline-delimited JSON response."""

    def __init__(self, queue: asyncio.Queue[object], started: float, model: str) -> None:
        self._queue = queue
        self._started = started
        self.model = model
        self.first_token_seconds: float | None = None
        self.completed_seconds: float | None = None
        self.text = ""

    def __aiter__(self) -> "LLMStream":
        return self

    async def __anext__(self) -> str:
        item = await self._queue.get()
        if item is _STREAM_END:
            self.completed_seconds = perf_counter() - self._started
            raise StopAsyncIteration
        if isinstance(item, Exception):
            raise item
        chunk = str(item)
        if self.first_token_seconds is None:
            self.first_token_seconds = perf_counter() - self._started
        self.text += chunk
        return chunk


_STREAM_END = object()


DEFAULT_SYSTEM_PROMPT = (
    "Είσαι το RobotOS, ένα φιλικό ρομπότ-βοηθός. "
    "Απαντάς αποκλειστικά στα ελληνικά, σύντομα, καθαρά και ευγενικά. "
    "Οι απαντήσεις σου θα εκφωνούνται, επομένως απόφυγε markdown, λίστες, "
    "emoji και περιττές επαναλήψεις. Ξεκίνα με σύντομη φυσική πρώτη πρόταση."
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

    def _messages(self, prompt: str, history: list[dict[str, str]] | None) -> list[dict[str, str]]:
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise LLMError("Δεν υπάρχει κείμενο για αποστολή στο Ollama.")
        messages: list[dict[str, str]] = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": clean_prompt})
        return messages

    def _request(self, prompt: str, history: list[dict[str, str]] | None, *, stream: bool) -> urllib.request.Request:
        body = json.dumps(
            {
                "model": self.model,
                "stream": stream,
                "think": False,
                "messages": self._messages(prompt, history),
                "options": {
                    "temperature": 0.2,
                    "num_predict": self.num_predict,
                    "num_ctx": self.num_ctx,
                },
            },
            ensure_ascii=False,
        ).encode("utf-8")
        return urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

    @staticmethod
    def _translate_error(exc: Exception) -> LLMError:
        if isinstance(exc, urllib.error.HTTPError):
            detail = exc.read().decode("utf-8", errors="replace").strip()
            return LLMError(f"Το Ollama επέστρεψε HTTP {exc.code}: {detail or exc.reason}")
        if isinstance(exc, urllib.error.URLError):
            return LLMError(
                "Δεν είναι δυνατή η σύνδεση με το Ollama. "
                "Βεβαιώσου ότι η υπηρεσία Ollama εκτελείται."
            )
        if isinstance(exc, (TimeoutError, OSError)):
            return LLMError(f"Η επικοινωνία με το Ollama απέτυχε: {exc}")
        if isinstance(exc, (UnicodeDecodeError, json.JSONDecodeError)):
            return LLMError("Το Ollama επέστρεψε μη έγκυρη απάντηση JSON.")
        if isinstance(exc, LLMError):
            return exc
        return LLMError(f"Η παραγωγή απάντησης απέτυχε: {exc}")

    def _generate_sync(self, prompt: str, history: list[dict[str, str]] | None = None) -> LLMResult:
        request = self._request(prompt, history, stream=False)
        try:
            with self._urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise self._translate_error(exc) from exc
        try:
            text = str(payload["message"]["content"]).strip()
        except (KeyError, TypeError) as exc:
            raise LLMError("Η απάντηση του Ollama δεν περιέχει κείμενο.") from exc
        if not text:
            raise LLMError("Το Ollama επέστρεψε κενή απάντηση.")
        return LLMResult(text=text, model=str(payload.get("model", self.model)))

    async def generate(self, prompt: str, history: list[dict[str, str]] | None = None) -> LLMResult:
        """Generate a completed reply with optional short-term history."""
        return await asyncio.to_thread(self._generate_sync, prompt, history)

    async def stream(self, prompt: str, history: list[dict[str, str]] | None = None) -> LLMStream:
        """Start an Ollama token stream without blocking the asyncio event loop."""
        # Validate before starting the worker thread so empty prompts fail immediately.
        request = self._request(prompt, history, stream=True)
        queue: asyncio.Queue[object] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        started = perf_counter()
        result = LLMStream(queue, started, self.model)

        def publish(item: object) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, item)

        def worker() -> None:
            seen_text = False
            try:
                with self._urlopen(request, timeout=self.timeout_seconds) as response:
                    for raw_line in response:
                        if not raw_line:
                            continue
                        line = raw_line.decode("utf-8").strip()
                        if not line:
                            continue
                        payload = json.loads(line)
                        model = payload.get("model")
                        if model:
                            result.model = str(model)
                        chunk = str(payload.get("message", {}).get("content", ""))
                        if chunk:
                            seen_text = True
                            publish(chunk)
                        if payload.get("done"):
                            break
                if not seen_text:
                    publish(LLMError("Το Ollama επέστρεψε κενή απάντηση."))
            except Exception as exc:
                publish(self._translate_error(exc))
            finally:
                publish(_STREAM_END)

        asyncio.create_task(asyncio.to_thread(worker), name="ollama-stream-worker")
        return result
