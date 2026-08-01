"""Handle user barge-in notifications from a Node."""
from __future__ import annotations

from loguru import logger
from websockets.asyncio.server import ServerConnection

from brain.services.speech import SpeechService
from shared.barge_in import SpeechInterruptPayload
from shared.models import Message


def create_speech_interrupt_handler(speech: SpeechService):
    async def handle(websocket: ServerConnection, message: Message) -> None:
        payload = SpeechInterruptPayload.from_message(message)
        speech.cancel_for(websocket)
        logger.info("Speech interrupted by Node: reason={}", payload.reason)

    return handle
