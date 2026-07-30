"""Tests for B1.9 conversation quality services."""

from __future__ import annotations

import asyncio
import json

from brain.services.conversation import ConversationLogger, ConversationMemory, TranscriptFilter


def test_conversation_memory_keeps_bounded_turns() -> None:
    memory = ConversationMemory(max_turns=2)
    owner = object()
    memory.add(owner, "ένα", "α")
    memory.add(owner, "δύο", "β")
    memory.add(owner, "τρία", "γ")

    assert memory.messages(owner) == [
        {"role": "user", "content": "δύο"},
        {"role": "assistant", "content": "β"},
        {"role": "user", "content": "τρία"},
        {"role": "assistant", "content": "γ"},
    ]


def test_transcript_filter_rejects_near_duplicate_in_window() -> None:
    now = [10.0]
    transcript_filter = TranscriptFilter(
        dedup_seconds=3.0,
        similarity_threshold=0.9,
        clock=lambda: now[0],
    )
    owner = object()

    assert transcript_filter.accept(owner, "Πώς σε λένε;")[0] is True
    now[0] = 11.0
    assert transcript_filter.accept(owner, "πως σε λενε")[0] is False
    now[0] = 14.1
    assert transcript_filter.accept(owner, "πως σε λενε")[0] is True


def test_conversation_logger_writes_utf8_jsonl(tmp_path) -> None:
    path = tmp_path / "conversations.jsonl"
    logger = ConversationLogger(path)

    asyncio.run(logger.append("Πώς σε λένε;", "Με λένε RobotOS.", "robot-greek"))

    record = json.loads(path.read_text(encoding="utf-8").strip())
    assert record["user"] == "Πώς σε λένε;"
    assert record["assistant"] == "Με λένε RobotOS."
    assert record["model"] == "robot-greek"
    assert record["timestamp"]
