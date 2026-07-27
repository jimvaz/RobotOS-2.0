"""Brain handler for incoming SPEECH commands."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from loguru import logger
from pydantic import ValidationError
from websockets.asyncio.server import ServerConnection

from brain.services import SpeechService
from shared.models import Message
from shared.protocol import MessageType
from shared.speech import SpeechPayload

SpeechHandler = Callable[[ServerConnection, Message], Awaitable[None]]


def create_speech_handler(service: SpeechService) -> SpeechHandler:
    """Create a handler that validates and forwards speech to connected nodes."""

    async def handle_speech(
        websocket: ServerConnection,
        message: Message,
    ) -> None:
        try:
            payload = SpeechPayload.from_message(message)
        except (ValidationError, ValueError) as exc:
            logger.warning("Invalid SPEECH payload: {}", exc)
            error = Message(
                type=MessageType.ERROR,
                payload={
                    "code": "invalid_speech",
                    "message": "The SPEECH payload is invalid.",
                    "reply_to": message.id,
                },
            )
            await websocket.send(error.to_json())
            return

        await service.say(
            payload.text,
            emotion=payload.emotion,
            exclude=websocket,
        )

    return handle_speech
