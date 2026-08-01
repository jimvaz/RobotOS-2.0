from __future__ import annotations
from loguru import logger
from pydantic import ValidationError
from shared.audio_playback import AudioPlaybackPayload
from shared.models import Message
from node.tts.audio_player import AudioPlaybackQueue

def create_audio_playback_handler(queue: AudioPlaybackQueue):
    async def handle(message: Message) -> None:
        try:
            payload = AudioPlaybackPayload.from_message(message)
            await queue.enqueue(payload.audio, payload.text, payload.engine)
        except (ValidationError, ValueError) as exc:
            logger.warning("Invalid AUDIO_PLAYBACK payload: {}", exc)
    return handle
