"""Microphone utterance recorder with simple RMS voice activity detection."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any


class AudioRecorderError(RuntimeError):
    """Raised when microphone capture cannot start or complete."""


@dataclass(frozen=True, slots=True)
class RecorderConfig:
    sample_rate: int = 16000
    channels: int = 1
    block_ms: int = 30
    speech_threshold: float = 0.015
    silence_ms: int = 700
    pre_buffer_ms: int = 300
    max_utterance_seconds: float = 15.0


class AudioRecorder:
    """Record one utterance as signed 16-bit little-endian mono PCM.

    Capture can be paused from the asyncio thread while the blocking audio
    stream runs in a worker thread. A pause immediately discards the current
    partial utterance so the robot's own speech is never sent to Whisper.
    """

    def __init__(self, config: RecorderConfig | None = None, sounddevice: Any | None = None) -> None:
        self.config = config or RecorderConfig()
        self._sounddevice = sounddevice
        self._capture_enabled = threading.Event()
        self._capture_enabled.set()
        self._generation_lock = threading.Lock()
        self._generation = 0

    @property
    def paused(self) -> bool:
        """Return whether microphone capture is currently suppressed."""

        return not self._capture_enabled.is_set()

    def _advance_generation(self) -> int:
        with self._generation_lock:
            self._generation += 1
            return self._generation

    @property
    def generation(self) -> int:
        with self._generation_lock:
            return self._generation

    def pause(self) -> None:
        """Suppress capture and invalidate every in-flight utterance."""

        self._capture_enabled.clear()
        self._advance_generation()

    def discard_pending(self) -> None:
        """Invalidate pre-buffered or completed audio from an older mic state."""

        self._advance_generation()

    def resume(self) -> None:
        """Allow a fresh capture generation to start again."""

        self._advance_generation()
        self._capture_enabled.set()

    async def wait_until_resumed(self, poll_seconds: float = 0.05) -> None:
        """Wait without blocking the event loop until capture is enabled."""

        while self.paused:
            await asyncio.sleep(poll_seconds)

    def _get_sounddevice(self) -> Any:
        if self._sounddevice is not None:
            return self._sounddevice
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise AudioRecorderError(
                "Το sounddevice δεν είναι εγκατεστημένο στον Node."
            ) from exc
        self._sounddevice = sd
        return sd

    def _record_sync(
        self,
        *,
        allow_while_paused: bool = False,
        speech_threshold: float | None = None,
        silence_ms: int | None = None,
        pre_buffer_ms: int | None = None,
        max_utterance_seconds: float | None = None,
    ) -> bytes:
        if self.paused and not allow_while_paused:
            return b""
        capture_generation = self.generation

        try:
            import numpy as np
        except ImportError as exc:
            raise AudioRecorderError("Το numpy δεν είναι εγκατεστημένο στον Node.") from exc

        sd = self._get_sounddevice()
        cfg = self.config
        blocksize = max(1, int(cfg.sample_rate * cfg.block_ms / 1000))
        threshold = cfg.speech_threshold if speech_threshold is None else speech_threshold
        end_silence_ms = cfg.silence_ms if silence_ms is None else silence_ms
        lead_ms = cfg.pre_buffer_ms if pre_buffer_ms is None else pre_buffer_ms
        max_seconds = (
            cfg.max_utterance_seconds
            if max_utterance_seconds is None
            else max_utterance_seconds
        )
        silence_blocks = max(1, end_silence_ms // cfg.block_ms)
        pre_blocks = max(1, lead_ms // cfg.block_ms)
        max_blocks = max(1, int(max_seconds * 1000 / cfg.block_ms))

        pre_buffer: list[bytes] = []
        captured: list[bytes] = []
        speaking = False
        silent_count = 0

        try:
            with sd.RawInputStream(
                samplerate=cfg.sample_rate,
                channels=cfg.channels,
                dtype="int16",
                blocksize=blocksize,
            ) as stream:
                for _ in range(max_blocks):
                    if (self.paused and not allow_while_paused) or self.generation != capture_generation:
                        return b""

                    data, overflowed = stream.read(blocksize)

                    if (self.paused and not allow_while_paused) or self.generation != capture_generation:
                        return b""
                    if overflowed:
                        continue

                    block = bytes(data)
                    samples = np.frombuffer(block, dtype="<i2").astype(np.float32)
                    rms = float(np.sqrt(np.mean(np.square(samples / 32768.0)))) if samples.size else 0.0

                    if not speaking:
                        pre_buffer.append(block)
                        pre_buffer = pre_buffer[-pre_blocks:]
                        if rms >= threshold:
                            speaking = True
                            captured.extend(pre_buffer)
                            pre_buffer.clear()
                        continue

                    captured.append(block)
                    if rms < threshold:
                        silent_count += 1
                        if silent_count >= silence_blocks:
                            break
                    else:
                        silent_count = 0
        except Exception as exc:
            raise AudioRecorderError(f"Αποτυχία καταγραφής μικροφώνου: {exc}") from exc

        if (self.paused and not allow_while_paused) or self.generation != capture_generation:
            return b""
        return b"".join(captured)

    async def record_utterance(self) -> bytes:
        return await asyncio.to_thread(self._record_sync)

    async def record_barge_in(
        self,
        *,
        speech_threshold: float,
        silence_ms: int,
        pre_buffer_ms: int,
        max_utterance_seconds: float,
    ) -> bytes:
        """Listen for a louder user utterance while robot audio is playing."""

        return await asyncio.to_thread(
            self._record_sync,
            allow_while_paused=True,
            speech_threshold=speech_threshold,
            silence_ms=silence_ms,
            pre_buffer_ms=pre_buffer_ms,
            max_utterance_seconds=max_utterance_seconds,
        )
