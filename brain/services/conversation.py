"""Conversation memory, transcript filtering, and durable logging."""

from __future__ import annotations

import asyncio
import json
import re
import time
import unicodedata
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, Hashable


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    user: str
    assistant: str


class ConversationMemory:
    """Keep a bounded short-term history for each connected node."""

    def __init__(self, max_turns: int = 10) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        self.max_turns = max_turns
        self._turns: dict[Hashable, deque[ConversationTurn]] = defaultdict(
            lambda: deque(maxlen=self.max_turns)
        )

    def add(self, owner: Hashable, user: str, assistant: str) -> None:
        clean_user = user.strip()
        clean_assistant = assistant.strip()
        if clean_user and clean_assistant:
            self._turns[owner].append(ConversationTurn(clean_user, clean_assistant))

    def messages(self, owner: Hashable) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for turn in self._turns.get(owner, ()):
            result.append({"role": "user", "content": turn.user})
            result.append({"role": "assistant", "content": turn.assistant})
        return result

    def clear(self, owner: Hashable) -> None:
        self._turns.pop(owner, None)


class TranscriptFilter:
    """Reject empty, hallucinated, low-confidence, and duplicate transcripts."""

    DEFAULT_HALLUCINATIONS = {
        "υποτιτλοι",
        "υποτιτλοι authorwave",
        "authorwave",
        "ευχαριστω που παρακολουθησατε",
        "σας ευχαριστω που παρακολουθησατε",
        "ευχαριστουμε που παρακολουθησατε",
        "thanks for watching",
        "subtitles authorwave",
    }

    def __init__(
        self,
        dedup_seconds: float = 3.0,
        similarity_threshold: float = 0.92,
        min_duration_seconds: float = 0.90,
        min_rms: float = 0.006,
        max_no_speech_probability: float = 0.75,
        min_average_log_probability: float = -1.20,
        hallucinations: set[str] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.dedup_seconds = max(0.0, dedup_seconds)
        self.similarity_threshold = min(1.0, max(0.0, similarity_threshold))
        self.min_duration_seconds = max(0.0, min_duration_seconds)
        self.min_rms = max(0.0, min_rms)
        self.max_no_speech_probability = min(1.0, max(0.0, max_no_speech_probability))
        self.min_average_log_probability = min_average_log_probability
        self._clock = clock
        source = hallucinations if hallucinations is not None else self.DEFAULT_HALLUCINATIONS
        self.hallucinations = {self.normalize(item) for item in source}
        self._last: dict[Hashable, tuple[str, float]] = {}

    @staticmethod
    def normalize(text: str) -> str:
        lowered = text.casefold().strip()
        lowered = "".join(
            char for char in unicodedata.normalize("NFD", lowered)
            if unicodedata.category(char) != "Mn"
        )
        lowered = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
        return " ".join(lowered.split())

    def accept(
        self,
        owner: Hashable,
        text: str,
        *,
        duration_seconds: float | None = None,
        rms: float | None = None,
        no_speech_probability: float | None = None,
        average_log_probability: float | None = None,
    ) -> tuple[bool, str]:
        normalized = self.normalize(text)
        if duration_seconds is not None and duration_seconds < self.min_duration_seconds:
            return False, "too_short"
        if rms is not None and rms < self.min_rms:
            return False, "low_rms"
        if not normalized:
            return False, "empty"
        if normalized in self.hallucinations:
            return False, "known_hallucination"
        if (
            no_speech_probability is not None
            and no_speech_probability > self.max_no_speech_probability
        ):
            return False, "no_speech"
        if (
            average_log_probability is not None
            and average_log_probability < self.min_average_log_probability
        ):
            return False, "low_confidence"

        now = self._clock()
        previous = self._last.get(owner)
        if previous is not None:
            previous_text, previous_at = previous
            if now - previous_at <= self.dedup_seconds:
                similarity = SequenceMatcher(None, previous_text, normalized).ratio()
                if similarity >= self.similarity_threshold:
                    return False, "duplicate"
        self._last[owner] = (normalized, now)
        return True, "accepted"

    def clear(self, owner: Hashable) -> None:
        self._last.pop(owner, None)


class ConversationLogger:
    """Append completed turns to a UTF-8 JSON Lines file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()

    async def append(self, user: str, assistant: str, model: str) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": user.strip(),
            "assistant": assistant.strip(),
            "model": model,
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        async with self._lock:
            await asyncio.to_thread(self._append_sync, line)

    def _append_sync(self, line: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
