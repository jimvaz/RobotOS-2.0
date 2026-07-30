"""Asynchronous speech queue for the RobotOS Node."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Protocol

from loguru import logger

SpeechHook = Callable[[], Awaitable[None]]


class SpeechEngine(Protocol):
    """Minimal interface implemented by Node text-to-speech engines."""

    async def speak(self, text: str) -> None:
        """Synthesize and play one text."""


@dataclass(frozen=True, slots=True)
class SpeechJob:
    """One queued speech request."""

    text: str


class SpeechQueue:
    """Serialize speech requests without blocking the WebSocket receiver."""

    def __init__(
        self,
        engine: SpeechEngine,
        *,
        on_speech_start: SpeechHook | None = None,
        on_speech_end: SpeechHook | None = None,
    ) -> None:
        self.engine = engine
        self._on_speech_start = on_speech_start
        self._on_speech_end = on_speech_end
        self._queue: asyncio.Queue[SpeechJob] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._stopping = False
        self._speaking = False

    @property
    def pending(self) -> int:
        """Return the number of speech jobs waiting to be processed."""

        return self._queue.qsize()

    @property
    def running(self) -> bool:
        """Return whether the queue worker is active."""

        return self._worker is not None and not self._worker.done()

    @property
    def speaking(self) -> bool:
        """Return whether Piper playback is currently active."""

        return self._speaking

    def start(self) -> None:
        """Start the background worker in the current event loop."""

        if self.running:
            return

        self._stopping = False
        self._worker = asyncio.create_task(
            self._run(),
            name="node-speech-worker",
        )
        logger.info("Speech queue started")

    async def enqueue(self, text: str) -> None:
        """Add a non-empty speech request to the queue."""

        clean_text = text.strip()
        if not clean_text:
            logger.warning("Ignored empty speech request")
            return

        if self._stopping:
            logger.warning("Speech queue is stopping; request ignored")
            return

        if not self.running:
            self.start()

        await self._queue.put(SpeechJob(text=clean_text))
        logger.info("[SPEECH] queued: {!r}", clean_text)

    async def join(self) -> None:
        """Wait until all currently queued jobs have been processed."""

        await self._queue.join()

    async def stop(self, *, drain: bool = True) -> None:
        """Stop the worker, optionally finishing queued speech first."""

        self._stopping = True

        if drain:
            await self._queue.join()

        worker = self._worker
        self._worker = None

        if worker is not None:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker

        logger.info("Speech queue stopped")

    async def _call_hook(self, hook: SpeechHook | None, name: str) -> None:
        if hook is None:
            return
        try:
            await hook()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Speech lifecycle hook failed: {}", name)

    async def _run(self) -> None:
        """Process speech requests sequentially until cancelled."""

        while True:
            job = await self._queue.get()

            try:
                self._speaking = True
                await self._call_hook(self._on_speech_start, "start")
                logger.info("[SPEECH] started: {!r}", job.text)
                await self.engine.speak(job.text)
                logger.info("[SPEECH] finished: {!r}", job.text)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[SPEECH] failed: {!r}", job.text)
            finally:
                self._speaking = False
                await self._call_hook(self._on_speech_end, "end")
                self._queue.task_done()
