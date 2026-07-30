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

    @property
    def paused(self) -> bool:
        """Return whether microphone capture is currently suppressed."""

        return not self._capture_enabled.is_set()

    def pause(self) -> None:
        """Suppress capture and interrupt the current utterance."""

        self._capture_enabled.clear()

    def resume(self) -> None:
        """Allow capture to start again."""

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

    def _record_sync(self) -> bytes:
        if self.paused:
            return b""

        try:
            import numpy as np
        except ImportError as exc:
            raise AudioRecorderError("Το numpy δεν είναι εγκατεστημένο στον Node.") from exc

        sd = self._get_sounddevice()
        cfg = self.config
        blocksize = max(1, int(cfg.sample_rate * cfg.block_ms / 1000))
        silence_blocks = max(1, cfg.silence_ms // cfg.block_ms)
        pre_blocks = max(1, cfg.pre_buffer_ms // cfg.block_ms)
        max_blocks = max(1, int(cfg.max_utterance_seconds * 1000 / cfg.block_ms))

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
                    if self.paused:
                        return b""

                    data, overflowed = stream.read(blocksize)

                    if self.paused:
                        return b""
                    if overflowed:
                        continue

                    block = bytes(data)
                    samples = np.frombuffer(block, dtype="<i2").astype(np.float32)
                    rms = float(np.sqrt(np.mean(np.square(samples / 32768.0)))) if samples.size else 0.0

                    if not speaking:
                        pre_buffer.append(block)
                        pre_buffer = pre_buffer[-pre_blocks:]
                        if rms >= cfg.speech_threshold:
                            speaking = True
                            captured.extend(pre_buffer)
                            pre_buffer.clear()
                        continue

                    captured.append(block)
                    if rms < cfg.speech_threshold:
                        silent_count += 1
                        if silent_count >= silence_blocks:
                            break
                    else:
                        silent_count = 0
        except Exception as exc:
            raise AudioRecorderError(f"Αποτυχία καταγραφής μικροφώνου: {exc}") from exc

        if self.paused:
            return b""
        return b"".join(captured)

    async def record_utterance(self) -> bytes:
        return await asyncio.to_thread(self._record_sync)
