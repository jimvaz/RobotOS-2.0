"""Brain speech delivery with optional local high-quality synthesis."""
from __future__ import annotations

from loguru import logger
from websockets.asyncio.server import ServerConnection

from brain.connection_manager import ConnectionManager
from brain.services.tts import TTSBackend, TTSError
from shared.audio_playback import (
    AudioPlaybackChunkPayload,
    AudioPlaybackEndPayload,
    AudioPlaybackStartPayload,
)
from shared.speech import SpeechPayload


class SpeechService:
    def __init__(
        self,
        connections: ConnectionManager,
        *,
        backend: TTSBackend | None = None,
        fallback_to_node: bool = True,
        chunk_size: int = 48 * 1024,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self._connections = connections
        self._backend = backend
        self._fallback_to_node = fallback_to_node
        self._chunk_size = chunk_size

    async def say(
        self,
        text: str,
        *,
        emotion: str | None = None,
        exclude: ServerConnection | None = None,
    ) -> int:
        clean = text.strip()
        audio: bytes | None = None
        if self._backend is not None:
            try:
                audio = await self._backend.synthesize(clean)
                logger.info(
                    "High-quality TTS generated: engine={}, bytes={}",
                    self._backend.name,
                    len(audio),
                )
            except TTSError as exc:
                logger.error("High-quality TTS failed: {}", exc)
                if not self._fallback_to_node:
                    raise

        delivered = 0
        for websocket in tuple(self._connections.connections):
            if websocket is exclude:
                continue
            try:
                if audio is None:
                    await websocket.send(
                        SpeechPayload(text=clean, emotion=emotion).to_message().to_json()
                    )
                else:
                    await self._send_audio_stream(websocket, audio, clean)
            except Exception:
                logger.exception("Failed to deliver speech")
                await self._connections.disconnect(websocket)
            else:
                delivered += 1

        if audio is None:
            logger.info("Using Node Piper fallback")
        logger.info("Speech dispatched: recipients={}, text={!r}", delivered, clean)
        return delivered

    async def _send_audio_stream(
        self,
        websocket: ServerConnection,
        audio: bytes,
        text: str,
    ) -> None:
        start = AudioPlaybackStartPayload.create(
            total_bytes=len(audio),
            chunk_size=self._chunk_size,
            text=text,
            engine=self._backend.name if self._backend else "unknown",
        )
        await websocket.send(start.to_message().to_json())

        chunks = 0
        for sequence, offset in enumerate(range(0, len(audio), self._chunk_size)):
            chunk = audio[offset : offset + self._chunk_size]
            await websocket.send(
                AudioPlaybackChunkPayload(
                    stream_id=start.stream_id,
                    sequence=sequence,
                    audio=chunk,
                ).to_message().to_json()
            )
            chunks += 1

        await websocket.send(
            AudioPlaybackEndPayload(
                stream_id=start.stream_id,
                chunks=chunks,
                total_bytes=len(audio),
            ).to_message().to_json()
        )
        logger.info(
            "Audio stream dispatched: id={}, chunks={}, bytes={}, chunk_size={}",
            start.stream_id,
            chunks,
            len(audio),
            self._chunk_size,
        )

    async def close(self) -> None:
        """Release resources held by the configured TTS backend."""
        if self._backend is not None:
            close = getattr(self._backend, "close", None)
            if close is not None:
                await close()
