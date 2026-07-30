"""Node handler for SPEECH messages."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from loguru import logger
from pydantic import ValidationError

from node.tts import SpeechQueue
from shared.models import Message
from shared.speech import SpeechPayload

NodeSpeechHandler = Callable[[Message], Awaitable[None]]


def create_speech_handler(speech_queue: SpeechQueue) -> NodeSpeechHandler:
    """Create a SPEECH handler backed by the Node speech queue."""

    async def handle_speech(message: Message) -> None:
        try:
            payload = SpeechPayload.from_message(message)
        except (ValidationError, ValueError) as exc:
            logger.warning("Invalid SPEECH message received from Brain: {}", exc)
            return

        await speech_queue.enqueue(payload.text, payload.emotion)

    return handle_speech
