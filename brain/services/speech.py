"""Brain speech delivery with low-latency sentence-first synthesis."""
from __future__ import annotations

import re
from time import perf_counter
from uuid import uuid4

from loguru import logger
from websockets.asyncio.server import ServerConnection

from brain.connection_manager import ConnectionManager
from brain.services.tts import TTSBackend, TTSError
from shared.audio_playback import (
    AudioPlaybackCancelPayload,
    AudioPlaybackChunkPayload,
    AudioPlaybackEndPayload,
    AudioPlaybackStartPayload,
)
from shared.speech import SpeechPayload

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!;;?…])\s+")


def split_for_fast_speech(text: str, *, max_chars: int = 150) -> list[str]:
    """Split spoken text into short natural segments without changing wording."""

    clean = " ".join(text.split())
    if not clean:
        return []

    sentences = [part.strip() for part in _SENTENCE_BOUNDARY.split(clean) if part.strip()]
    segments: list[str] = []
    for sentence in sentences:
        if len(sentence) <= max_chars:
            segments.append(sentence)
            continue

        # Long sentences are split at natural comma/colon boundaries first.
        pieces = [piece.strip() for piece in re.split(r"(?<=[,:])\s+", sentence) if piece.strip()]
        current = ""
        for piece in pieces:
            candidate = f"{current} {piece}".strip()
            if current and len(candidate) > max_chars:
                segments.append(current)
                current = piece
            else:
                current = candidate
        if current:
            segments.append(current)

    return segments or [clean]


class SpeechService:
    def __init__(
        self,
        connections: ConnectionManager,
        *,
        backend: TTSBackend | None = None,
        fallback_to_node: bool = True,
        chunk_size: int = 48 * 1024,
        segment_max_chars: int = 150,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if segment_max_chars < 40:
            raise ValueError("segment_max_chars must be at least 40")
        self._connections = connections
        self._backend = backend
        self._fallback_to_node = fallback_to_node
        self._chunk_size = chunk_size
        self._segment_max_chars = segment_max_chars
        self._cancelled: set[ServerConnection] = set()

    def cancel_for(self, websocket: ServerConnection) -> None:
        """Request cancellation of the current outgoing stream for one Node."""
        self._cancelled.add(websocket)

    async def say(
        self,
        text: str,
        *,
        emotion: str | None = None,
        exclude: ServerConnection | None = None,
    ) -> int:
        clean = text.strip()
        recipients = [
            websocket
            for websocket in tuple(self._connections.connections)
            if websocket is not exclude
        ]
        if not recipients:
            logger.info("Speech dispatched: recipients=0, text={!r}", clean)
            return 0

        if self._backend is None:
            return await self._send_text_fallback(recipients, clean, emotion)

        segments = split_for_fast_speech(clean, max_chars=self._segment_max_chars)
        speech_id = str(uuid4())
        active = set(recipients)
        first_audio_ready: float | None = None
        started = perf_counter()

        for index, segment in enumerate(segments):
            segment_started = perf_counter()
            try:
                try:
                    audio = await self._backend.synthesize(segment, emotion=emotion)
                except TypeError:
                    audio = await self._backend.synthesize(segment)
            except TTSError as exc:
                logger.error(
                    "High-quality TTS failed at segment {}/{}: {}",
                    index + 1,
                    len(segments),
                    exc,
                )
                await self._cancel_sequence(active, speech_id, str(exc))
                if self._fallback_to_node:
                    remaining = " ".join(segments[index:])
                    await self._send_text_fallback(list(active), remaining, emotion)
                elif index == 0:
                    raise
                break

            synthesis_seconds = perf_counter() - segment_started
            if first_audio_ready is None:
                first_audio_ready = perf_counter() - started
                logger.info(
                    "Fast speech first audio ready: {:.2f}s, segment={!r}",
                    first_audio_ready,
                    segment,
                )
            logger.info(
                "TTS segment generated: {}/{}, seconds={:.2f}, bytes={}, text={!r}",
                index + 1,
                len(segments),
                synthesis_seconds,
                len(audio),
                segment,
            )

            final_segment = index == len(segments) - 1
            for websocket in tuple(active):
                try:
                    await self._send_audio_stream(
                        websocket,
                        audio,
                        segment,
                        speech_id=speech_id,
                        segment_index=index,
                        segment_count=len(segments),
                        final_segment=final_segment,
                    )
                except Exception:
                    logger.exception("Failed to deliver speech segment")
                    active.discard(websocket)
                    await self._connections.disconnect(websocket)

            if not active:
                break

        delivered = len(active)
        logger.info(
            "Speech dispatched: recipients={}, segments={}, text={!r}",
            delivered,
            len(segments),
            clean,
        )
        return delivered

    async def _send_text_fallback(
        self,
        recipients: list[ServerConnection],
        text: str,
        emotion: str | None,
    ) -> int:
        delivered = 0
        for websocket in tuple(recipients):
            try:
                await websocket.send(
                    SpeechPayload(text=text, emotion=emotion).to_message().to_json()
                )
            except Exception:
                logger.exception("Failed to deliver Node Piper fallback")
                await self._connections.disconnect(websocket)
            else:
                delivered += 1
        logger.info("Using Node Piper fallback")
        return delivered

    async def _cancel_sequence(
        self,
        recipients: set[ServerConnection],
        speech_id: str,
        reason: str,
    ) -> None:
        message = AudioPlaybackCancelPayload(speech_id=speech_id, reason=reason).to_message().to_json()
        for websocket in tuple(recipients):
            try:
                await websocket.send(message)
            except Exception:
                recipients.discard(websocket)
                await self._connections.disconnect(websocket)

    async def _send_audio_stream(
        self,
        websocket: ServerConnection,
        audio: bytes,
        text: str,
        *,
        speech_id: str,
        segment_index: int,
        segment_count: int,
        final_segment: bool,
    ) -> None:
        self._cancelled.discard(websocket)
        start = AudioPlaybackStartPayload.create(
            total_bytes=len(audio),
            chunk_size=self._chunk_size,
            text=text,
            engine=self._backend.name if self._backend else "unknown",
            speech_id=speech_id,
            segment_index=segment_index,
            segment_count=segment_count,
        )
        await websocket.send(start.to_message().to_json())

        chunks = 0
        for sequence, offset in enumerate(range(0, len(audio), self._chunk_size)):
            if websocket in self._cancelled:
                logger.info("Audio stream cancelled before chunk {}: id={}", sequence, start.stream_id)
                self._cancelled.discard(websocket)
                await websocket.send(
                    AudioPlaybackCancelPayload(
                        speech_id=speech_id,
                        reason="cancelled",
                    ).to_message().to_json()
                )
                return
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
                speech_id=speech_id,
                segment_index=segment_index,
                segment_count=segment_count,
                final_segment=final_segment,
            ).to_message().to_json()
        )
        logger.info(
            "Audio segment dispatched: speech={}, segment={}/{}, chunks={}, bytes={}",
            speech_id,
            segment_index + 1,
            segment_count,
            chunks,
            len(audio),
        )

    async def preload(self) -> None:
        if self._backend is not None:
            preload = getattr(self._backend, "preload", None)
            if preload is not None:
                await preload()

    async def close(self) -> None:
        if self._backend is not None:
            close = getattr(self._backend, "close", None)
            if close is not None:
                await close()
