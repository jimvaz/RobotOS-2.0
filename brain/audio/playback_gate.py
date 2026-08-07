"""Coordinate the local Brain microphone with real Node playback state."""
from __future__ import annotations

import asyncio
from loguru import logger


class PlaybackGate:
    """Hard-lock the Brain microphone until the Node confirms playback finished."""

    def __init__(self, cooldown_seconds: float = 0.5) -> None:
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self._active_speeches: set[str] = set()
        self._changed = asyncio.Event()
        self._changed.set()
        self._release_task: asyncio.Task[None] | None = None

    @property
    def blocked(self) -> bool:
        return bool(self._active_speeches) or (self._release_task is not None and not self._release_task.done())

    def begin(self, speech_id: str) -> None:
        if self._release_task is not None and not self._release_task.done():
            self._release_task.cancel()
        self._release_task = None
        self._active_speeches.add(speech_id)
        self._changed.clear()
        logger.info("PC MIC hard-locked for playback: speech={}", speech_id)

    async def finish(self, speech_id: str) -> None:
        if speech_id not in self._active_speeches:
            logger.debug("Ignoring playback ACK for inactive speech={}", speech_id)
            return
        self._active_speeches.discard(speech_id)
        if self._active_speeches:
            return
        if self._release_task is not None and not self._release_task.done():
            self._release_task.cancel()
        self._release_task = asyncio.create_task(self._release_after_cooldown(speech_id))

    async def cancel(self, speech_id: str) -> None:
        self._active_speeches.discard(speech_id)
        if not self._active_speeches:
            if self._release_task is not None and not self._release_task.done():
                self._release_task.cancel()
            self._release_task = None
            self._changed.set()
            logger.info("PC MIC playback lock cancelled: speech={}", speech_id)

    async def _release_after_cooldown(self, speech_id: str) -> None:
        try:
            if self.cooldown_seconds:
                await asyncio.sleep(self.cooldown_seconds)
            if not self._active_speeches:
                self._changed.set()
                logger.info("PC MIC unlocked after playback ACK + {:.0f} ms cooldown: speech={}", self.cooldown_seconds * 1000, speech_id)
        finally:
            self._release_task = None

    async def wait_until_open(self) -> None:
        while self.blocked:
            await self._changed.wait()
