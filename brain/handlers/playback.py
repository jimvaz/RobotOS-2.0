"""Handle authoritative playback completion acknowledgements from Nodes."""
from __future__ import annotations
from loguru import logger
from pydantic import ValidationError
from websockets.asyncio.server import ServerConnection
from brain.audio.playback_gate import PlaybackGate
from shared.audio_playback import AudioPlaybackFinishedPayload
from shared.models import Message


def create_playback_finished_handler(gate: PlaybackGate):
    async def handle(websocket: ServerConnection, message: Message) -> None:
        try:
            payload = AudioPlaybackFinishedPayload.from_message(message)
        except (ValidationError, ValueError) as exc:
            logger.warning("Invalid AUDIO_PLAYBACK_FINISHED payload: {}", exc)
            return
        logger.info("Playback finished ACK received: speech={}", payload.speech_id)
        await gate.finish(payload.speech_id)
    return handle
