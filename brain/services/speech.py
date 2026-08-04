"""Brain speech delivery with low-latency sentence-first synthesis."""
from __future__ import annotations

import re
from collections.abc import AsyncIterator, Callable
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
_SENTENCE_END = re.compile(r"[.!;;?…](?:[\"'»”)]*)\s*$")


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


def _pop_complete_segments(buffer: str, *, max_chars: int) -> tuple[list[str], str]:
    """Remove complete spoken segments from an incremental text buffer."""
    normalized = re.sub(r"\s+", " ", buffer)
    pieces = _SENTENCE_BOUNDARY.split(normalized)
    complete: list[str] = []
    remainder = ""
    for index, piece in enumerate(pieces):
        part = piece.strip()
        if not part:
            continue
        is_last = index == len(pieces) - 1
        if is_last and not _SENTENCE_END.search(part):
            remainder = part
        else:
            complete.extend(split_for_fast_speech(part, max_chars=max_chars))
    # A model may produce a long sentence without punctuation. Cut only at a natural
    # comma or whitespace once the buffer becomes large enough to hurt TTS latency.
    if len(remainder) > max_chars:
        cut = max(remainder.rfind(", ", 0, max_chars), remainder.rfind(" ", 0, max_chars))
        if cut >= 40:
            complete.append(remainder[: cut + 1].strip())
            remainder = remainder[cut + 1 :].strip()
    return complete, remainder


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
        self._cancelled.add(websocket)

    async def say(self, text: str, *, emotion: str | None = None, exclude: ServerConnection | None = None) -> int:
        clean = text.strip()
        recipients = [ws for ws in tuple(self._connections.connections) if ws is not exclude]
        if not recipients:
            logger.info("Speech dispatched: recipients=0, text={!r}", clean)
            return 0
        if self._backend is None:
            return await self._send_text_fallback(recipients, clean, emotion)

        segments = split_for_fast_speech(clean, max_chars=self._segment_max_chars)
        speech_id = str(uuid4())
        active = set(recipients)
        started = perf_counter()
        for index, segment in enumerate(segments):
            await self._synthesize_and_send(
                active,
                segment,
                speech_id=speech_id,
                segment_index=index,
                segment_count=len(segments),
                final_segment=index == len(segments) - 1,
                emotion=emotion,
                overall_started=started,
            )
            if not active:
                break
        logger.info("Speech dispatched: recipients={}, segments={}, text={!r}", len(active), len(segments), clean)
        return len(active)

    async def say_stream(
        self,
        chunks: AsyncIterator[str],
        *,
        emotion_for: Callable[[str], str | None] | None = None,
        transform: Callable[[str], str] | None = None,
        exclude: ServerConnection | None = None,
    ) -> tuple[int, str]:
        """Speak an incremental LLM response as soon as its first sentence is known.

        The newest complete sentence is held until either another token arrives or
        the stream ends. This lets the protocol mark the actual final segment while
        still dispatching the first sentence before the complete LLM reply exists.
        """
        recipients = [ws for ws in tuple(self._connections.connections) if ws is not exclude]
        active = set(recipients)
        if not active:
            text = "".join([chunk async for chunk in chunks]).strip()
            return 0, text
        if self._backend is None:
            text = "".join([chunk async for chunk in chunks]).strip()
            return await self._send_text_fallback(recipients, text, None), text

        speech_id = str(uuid4())
        started = perf_counter()
        first_sentence_at: float | None = None
        buffer = ""
        pending: str | None = None
        full_parts: list[str] = []
        segment_index = 0

        async for chunk in chunks:
            if not chunk:
                continue
            if buffer and chunk and not buffer[-1].isspace() and not chunk[0].isspace():
                buffer += " "
            buffer += chunk
            complete, buffer = _pop_complete_segments(buffer, max_chars=self._segment_max_chars)
            for segment in complete:
                if first_sentence_at is None:
                    first_sentence_at = perf_counter() - started
                    logger.info("LLM first sentence ready: {:.2f}s, text={!r}", first_sentence_at, segment)
                if pending is not None:
                    spoken = transform(pending) if transform else pending
                    full_parts.append(spoken)
                    emotion = emotion_for(spoken) if emotion_for else None
                    await self._synthesize_and_send(
                        active,
                        spoken,
                        speech_id=speech_id,
                        segment_index=segment_index,
                        segment_count=segment_index + 2,
                        final_segment=False,
                        emotion=emotion,
                        overall_started=started,
                    )
                    segment_index += 1
                pending = segment

            # Once any text for the next sentence has arrived, pending cannot be final.
            if pending is not None and buffer.strip():
                spoken = transform(pending) if transform else pending
                full_parts.append(spoken)
                emotion = emotion_for(spoken) if emotion_for else None
                await self._synthesize_and_send(
                    active,
                    spoken,
                    speech_id=speech_id,
                    segment_index=segment_index,
                    segment_count=segment_index + 2,
                    final_segment=False,
                    emotion=emotion,
                    overall_started=started,
                )
                segment_index += 1
                pending = None
            if not active:
                break

        tail = buffer.strip()
        if tail:
            if pending is not None:
                spoken = transform(pending) if transform else pending
                full_parts.append(spoken)
                emotion = emotion_for(spoken) if emotion_for else None
                await self._synthesize_and_send(
                    active,
                    spoken,
                    speech_id=speech_id,
                    segment_index=segment_index,
                    segment_count=segment_index + 2,
                    final_segment=False,
                    emotion=emotion,
                    overall_started=started,
                )
                segment_index += 1
            pending = tail

        if pending is not None and active:
            spoken = transform(pending) if transform else pending
            full_parts.append(spoken)
            emotion = emotion_for(spoken) if emotion_for else None
            await self._synthesize_and_send(
                active,
                spoken,
                speech_id=speech_id,
                segment_index=segment_index,
                segment_count=segment_index + 1,
                final_segment=True,
                emotion=emotion,
                overall_started=started,
            )
            segment_index += 1

        full_text = " ".join(part for part in full_parts if part).strip()
        logger.info(
            "Streaming speech dispatched: recipients={}, segments={}, seconds={:.2f}, text={!r}",
            len(active),
            segment_index,
            perf_counter() - started,
            full_text,
        )
        return len(active), full_text

    async def _synthesize_and_send(
        self,
        active: set[ServerConnection],
        segment: str,
        *,
        speech_id: str,
        segment_index: int,
        segment_count: int,
        final_segment: bool,
        emotion: str | None,
        overall_started: float,
    ) -> None:
        if not active:
            return
        segment_started = perf_counter()
        try:
            try:
                audio = await self._backend.synthesize(segment, emotion=emotion)  # type: ignore[union-attr]
            except TypeError:
                audio = await self._backend.synthesize(segment)  # type: ignore[union-attr]
        except TTSError as exc:
            logger.error("High-quality TTS failed at segment {}: {}", segment_index + 1, exc)
            await self._cancel_sequence(active, speech_id, str(exc))
            if self._fallback_to_node:
                await self._send_text_fallback(list(active), segment, emotion)
            else:
                raise
            return

        synthesis_seconds = perf_counter() - segment_started
        logger.info(
            "TTS segment ready: index={}, tts={:.2f}s, total_to_audio={:.2f}s, bytes={}, text={!r}",
            segment_index + 1,
            synthesis_seconds,
            perf_counter() - overall_started,
            len(audio),
            segment,
        )
        for websocket in tuple(active):
            try:
                await self._send_audio_stream(
                    websocket,
                    audio,
                    segment,
                    speech_id=speech_id,
                    segment_index=segment_index,
                    segment_count=segment_count,
                    final_segment=final_segment,
                )
            except Exception:
                logger.exception("Failed to deliver speech segment")
                active.discard(websocket)
                await self._connections.disconnect(websocket)

    async def _send_text_fallback(self, recipients: list[ServerConnection], text: str, emotion: str | None) -> int:
        delivered = 0
        for websocket in tuple(recipients):
            try:
                await websocket.send(SpeechPayload(text=text, emotion=emotion).to_message().to_json())
            except Exception:
                logger.exception("Failed to deliver Node Piper fallback")
                await self._connections.disconnect(websocket)
            else:
                delivered += 1
        logger.info("Using Node Piper fallback")
        return delivered

    async def _cancel_sequence(self, recipients: set[ServerConnection], speech_id: str, reason: str) -> None:
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
            segment_count=max(1, segment_count),
        )
        await websocket.send(start.to_message().to_json())
        chunks = 0
        for sequence, offset in enumerate(range(0, len(audio), self._chunk_size)):
            if websocket in self._cancelled:
                self._cancelled.discard(websocket)
                await websocket.send(AudioPlaybackCancelPayload(speech_id=speech_id, reason="cancelled").to_message().to_json())
                return
            chunk = audio[offset : offset + self._chunk_size]
            await websocket.send(AudioPlaybackChunkPayload(stream_id=start.stream_id, sequence=sequence, audio=chunk).to_message().to_json())
            chunks += 1
        await websocket.send(
            AudioPlaybackEndPayload(
                stream_id=start.stream_id,
                chunks=chunks,
                total_bytes=len(audio),
                speech_id=speech_id,
                segment_index=segment_index,
                segment_count=max(1, segment_count),
                final_segment=final_segment,
            ).to_message().to_json()
        )
        logger.info(
            "Audio segment dispatched: speech={}, segment={}, chunks={}, bytes={}, final={}",
            speech_id,
            segment_index + 1,
            chunks,
            len(audio),
            final_segment,
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
