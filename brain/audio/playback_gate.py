"""Coordinate the local Brain microphone with remote Node audio playback."""

from __future__ import annotations

import asyncio
import io
import time
import wave

from loguru import logger


class PlaybackGate:
    """Suppress local microphone capture while Nobi audio is expected to play."""

    def __init__(self, cooldown_seconds: float = 0.5) -> None:
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self._blocked_until = 0.0
        self._changed = asyncio.Event()
        self._changed.set()

    @property
    def blocked(self) -> bool:
        return time.monotonic() < self._blocked_until

    def reserve_seconds(self, seconds: float) -> None:
        now = time.monotonic()
        base = max(now, self._blocked_until)
        self._blocked_until = base + max(0.0, seconds) + self.cooldown_seconds
        self._changed.clear()
        logger.debug("PC microphone reserved for playback: {:.2f}s", seconds)

    def reserve_wav(self, audio: bytes) -> float:
        duration = 0.0
        try:
            with wave.open(io.BytesIO(audio), "rb") as wav_file:
                rate = wav_file.getframerate()
                duration = wav_file.getnframes() / float(rate) if rate else 0.0
        except (wave.Error, EOFError):
            # Conservative fallback for malformed/non-WAV data.
            duration = 1.0
        self.reserve_seconds(duration)
        return duration

    async def wait_until_open(self) -> None:
        while True:
            remaining = self._blocked_until - time.monotonic()
            if remaining <= 0:
                self._changed.set()
                return
            try:
                await asyncio.wait_for(self._changed.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                pass
