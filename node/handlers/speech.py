"""Node handler for SPEECH messages."""

from __future__ import annotations

from loguru import logger
from pydantic import ValidationError

from shared.models import Message
from shared.speech import SpeechPayload


async def handle_speech(message: Message) -> None:
    """Validate and log speech text received from the Brain.

    Piper playback is intentionally added in B1.5.2.
    """

    try:
        payload = SpeechPayload.from_message(message)
    except (ValidationError, ValueError) as exc:
        logger.warning("Invalid SPEECH message received from Brain: {}", exc)
        return

    logger.info("[SPEECH] {}", payload.text)
