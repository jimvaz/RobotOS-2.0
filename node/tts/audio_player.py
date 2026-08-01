"""Queue legacy WAV files and stream Brain-generated audio to the local player."""
from __future__ import annotations

import asyncio
import tempfile
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

Hook = Callable[[], Awaitable[None]]


@dataclass(slots=True)
class _ActiveStream:
    stream_id: str
    process: asyncio.subprocess.Process
    expected_sequence: int
    received_bytes: int
    total_bytes: int
    text: str
    engine: str


class AudioPlaybackQueue:
    """Play complete WAV payloads and incremental WAV byte streams."""

    def __init__(
        self,
        player: str = "aplay",
        *,
        on_start: Hook | None = None,
        on_end: Hook | None = None,
    ) -> None:
        self.player = player
        self.on_start = on_start
        self.on_end = on_end
        self.queue: asyncio.Queue[tuple[bytes, str, str]] = asyncio.Queue()
        self.worker: asyncio.Task[None] | None = None
        self._stream: _ActiveStream | None = None
        self._stream_lock = asyncio.Lock()
        self._legacy_process: asyncio.subprocess.Process | None = None

    @property
    def is_playing(self) -> bool:
        stream_playing = self._stream is not None
        legacy_playing = (
            self._legacy_process is not None
            and self._legacy_process.returncode is None
        )
        return stream_playing or legacy_playing

    def start(self) -> None:
        if self.worker is None or self.worker.done():
            self.worker = asyncio.create_task(self._run(), name="node-audio-playback")

    async def enqueue(self, audio: bytes, text: str = "", engine: str = "unknown") -> None:
        self.start()
        await self.queue.put((audio, text, engine))

    async def begin_stream(
        self,
        stream_id: str,
        *,
        total_bytes: int,
        text: str = "",
        engine: str = "unknown",
    ) -> None:
        async with self._stream_lock:
            await self._abort_stream_locked("replaced by a new stream")
            if self.on_start:
                await self.on_start()
            process = await asyncio.create_subprocess_exec(
                self.player,
                "-q",
                "-",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._stream = _ActiveStream(
                stream_id=stream_id,
                process=process,
                expected_sequence=0,
                received_bytes=0,
                total_bytes=total_bytes,
                text=text,
                engine=engine,
            )
            logger.info(
                "[AUDIO STREAM] started: id={}, engine={}, bytes={}, text={!r}",
                stream_id,
                engine,
                total_bytes,
                text,
            )

    async def write_stream_chunk(self, stream_id: str, sequence: int, audio: bytes) -> None:
        async with self._stream_lock:
            stream = self._stream
            if stream is None or stream.stream_id != stream_id:
                raise ValueError(f"Unknown audio stream {stream_id}")
            if sequence != stream.expected_sequence:
                raise ValueError(
                    f"Out-of-order audio chunk: expected {stream.expected_sequence}, got {sequence}"
                )
            if stream.process.stdin is None:
                raise RuntimeError("Audio player stdin is unavailable")
            stream.process.stdin.write(audio)
            await stream.process.stdin.drain()
            stream.expected_sequence += 1
            stream.received_bytes += len(audio)

    async def end_stream(self, stream_id: str, *, chunks: int, total_bytes: int) -> None:
        async with self._stream_lock:
            stream = self._stream
            if stream is None or stream.stream_id != stream_id:
                raise ValueError(f"Unknown audio stream {stream_id}")
            if chunks != stream.expected_sequence:
                raise ValueError(
                    f"Audio stream chunk count mismatch: expected {chunks}, received {stream.expected_sequence}"
                )
            if total_bytes != stream.received_bytes:
                raise ValueError(
                    f"Audio stream byte count mismatch: expected {total_bytes}, received {stream.received_bytes}"
                )
            if stream.process.stdin is not None:
                stream.process.stdin.close()
                with suppress(Exception):
                    await stream.process.stdin.wait_closed()
            _, stderr = await stream.process.communicate()
            try:
                if stream.process.returncode:
                    raise RuntimeError(stderr.decode(errors="replace"))
                logger.info(
                    "[AUDIO STREAM] finished: id={}, chunks={}, bytes={}",
                    stream_id,
                    chunks,
                    total_bytes,
                )
            finally:
                self._stream = None
                if self.on_end:
                    await self.on_end()

    async def abort_stream(self, reason: str = "aborted") -> None:
        async with self._stream_lock:
            await self._abort_stream_locked(reason)

    async def _abort_stream_locked(self, reason: str) -> None:
        stream = self._stream
        if stream is None:
            return
        logger.warning("[AUDIO STREAM] aborting id={}: {}", stream.stream_id, reason)
        if stream.process.stdin is not None:
            stream.process.stdin.close()
        if stream.process.returncode is None:
            stream.process.terminate()
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(stream.process.wait(), timeout=2)
        self._stream = None
        if self.on_end:
            await self.on_end()

    async def interrupt(self, reason: str = "user speech") -> None:
        """Immediately stop active playback and discard queued legacy audio."""

        await self.abort_stream(reason)
        process = self._legacy_process
        if process is not None and process.returncode is None:
            logger.warning("[AUDIO] interrupted: {}", reason)
            process.terminate()
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=2)
        while True:
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                self.queue.task_done()

    async def stop(self) -> None:
        await self.abort_stream("Node stopping")
        await self.queue.join()
        if self.worker:
            self.worker.cancel()
            with suppress(asyncio.CancelledError):
                await self.worker

    async def _run(self) -> None:
        while True:
            audio, text, engine = await self.queue.get()
            path: Path | None = None
            try:
                if self.on_start:
                    await self.on_start()
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as file:
                    file.write(audio)
                    path = Path(file.name)
                logger.info("[AUDIO] started: engine={}, text={!r}", engine, text)
                process = await asyncio.create_subprocess_exec(
                    self.player,
                    "-q",
                    str(path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                self._legacy_process = process
                _, stderr = await process.communicate()
                if process.returncode:
                    raise RuntimeError(stderr.decode(errors="replace"))
                logger.info("[AUDIO] finished")
            except Exception:
                logger.exception("Brain audio playback failed")
            finally:
                self._legacy_process = None
                if path:
                    path.unlink(missing_ok=True)
                if self.on_end:
                    await self.on_end()
                self.queue.task_done()
