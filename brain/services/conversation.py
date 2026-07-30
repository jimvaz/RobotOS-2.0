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
    """Reject empty, noise-like, and near-duplicate transcripts."""

    def __init__(
        self,
        dedup_seconds: float = 3.0,
        similarity_threshold: float = 0.92,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.dedup_seconds = max(0.0, dedup_seconds)
        self.similarity_threshold = min(1.0, max(0.0, similarity_threshold))
        self._clock = clock
        self._last: dict[Hashable, tuple[str, float]] = {}

    @staticmethod
    def normalize(text: str) -> str:
        lowered = text.casefold().strip()
        lowered = "".join(
            char for char in unicodedata.normalize("NFD", lowered)
            if unicodedata.category(char) != "Mn"
        )
        lowered = re.sub(r"[^\w\sάέήίόύώϊϋΐΰ]", " ", lowered, flags=re.UNICODE)
        return " ".join(lowered.split())

    def accept(self, owner: Hashable, text: str) -> tuple[bool, str]:
        normalized = self.normalize(text)
        if not normalized:
            return False, "empty"
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
