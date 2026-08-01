from __future__ import annotations

from loguru import logger
from pydantic import ValidationError

from node.tts.audio_player import AudioPlaybackQueue
from shared.audio_playback import (
    AudioPlaybackChunkPayload,
    AudioPlaybackEndPayload,
    AudioPlaybackPayload,
    AudioPlaybackStartPayload,
)
from shared.models import Message


def create_audio_playback_handler(queue: AudioPlaybackQueue):
    """Handle the legacy one-message audio payload."""

    async def handle(message: Message) -> None:
        try:
            payload = AudioPlaybackPayload.from_message(message)
            await queue.enqueue(payload.audio, payload.text, payload.engine)
        except (ValidationError, ValueError) as exc:
            logger.warning("Invalid AUDIO_PLAYBACK payload: {}", exc)

    return handle


def create_audio_stream_handlers(queue: AudioPlaybackQueue):
    async def handle_start(message: Message) -> None:
        try:
            payload = AudioPlaybackStartPayload.from_message(message)
            await queue.begin_stream(
                payload.stream_id,
                total_bytes=payload.total_bytes,
                text=payload.text,
                engine=payload.engine,
            )
        except (ValidationError, ValueError, RuntimeError) as exc:
            logger.warning("Invalid AUDIO_PLAYBACK_START payload: {}", exc)
            await queue.abort_stream(str(exc))

    async def handle_chunk(message: Message) -> None:
        try:
            payload = AudioPlaybackChunkPayload.from_message(message)
            await queue.write_stream_chunk(
                payload.stream_id,
                payload.sequence,
                payload.audio,
            )
        except (ValidationError, ValueError, RuntimeError) as exc:
            logger.warning("Invalid AUDIO_PLAYBACK_CHUNK payload: {}", exc)
            await queue.abort_stream(str(exc))

    async def handle_end(message: Message) -> None:
        try:
            payload = AudioPlaybackEndPayload.from_message(message)
            await queue.end_stream(
                payload.stream_id,
                chunks=payload.chunks,
                total_bytes=payload.total_bytes,
            )
        except (ValidationError, ValueError, RuntimeError) as exc:
            logger.warning("Invalid AUDIO_PLAYBACK_END payload: {}", exc)
            await queue.abort_stream(str(exc))

    return handle_start, handle_chunk, handle_end
