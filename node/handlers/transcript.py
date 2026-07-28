"""Handle Whisper transcripts returned by the Brain."""

from __future__ import annotations

from loguru import logger

from shared.audio import TranscriptPayload
from shared.models import Message


async def handle_transcript(message: Message) -> None:
    payload = TranscriptPayload.from_message(message)
    logger.info("[TRANSCRIPT] {}", payload.text or "<κενό>")
