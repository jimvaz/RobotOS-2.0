"""Low-latency local microphone capture for the Windows Brain."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from time import perf_counter
from typing import Awaitable, Callable

from loguru import logger

from brain.audio.playback_gate import PlaybackGate


class LocalMicrophoneError(RuntimeError):
    """Raised when the local PC microphone cannot be used."""


@dataclass(frozen=True, slots=True)
class LocalMicrophoneConfig:
    device: int | str | None = None
    capture_rate: int = 48000
    target_rate: int = 16000
    channels: int = 1
    block_ms: int = 20
    speech_threshold: float = 0.010
    silence_ms: int = 650
    pre_buffer_ms: int = 300
    max_seconds: float = 30.0
    adaptive_listening: bool = True
    medium_after_seconds: float = 3.0
    long_after_seconds: float = 7.0
    medium_silence_ms: int = 850
    long_silence_ms: int = 1200
    retry_delay: float = 0.25
    language: str = "el"


class LocalMicrophoneListener:
    """Capture complete utterances and submit 16 kHz mono int16 PCM to Brain."""

    def __init__(
        self,
        config: LocalMicrophoneConfig,
        submit: Callable[[bytes, int, str], Awaitable[None]],
        playback_gate: PlaybackGate,
    ) -> None:
        self.config = config
        self.submit = submit
        self.playback_gate = playback_gate
        self.running = True

    def stop(self) -> None:
        self.running = False

    def _endpoint_silence_ms(self, speech_seconds: float) -> int:
        """Return the silence window used to decide that the user finished speaking.

        Short requests stay responsive, while longer requests tolerate natural
        thinking pauses. ROBOTOS_BRAIN_MIC_SILENCE_MS remains the short/fallback
        window, so existing deployments keep their explicit preference.
        """
        cfg = self.config
        if not cfg.adaptive_listening:
            return cfg.silence_ms
        if speech_seconds >= cfg.long_after_seconds:
            return max(cfg.silence_ms, cfg.long_silence_ms)
        if speech_seconds >= cfg.medium_after_seconds:
            return max(cfg.silence_ms, cfg.medium_silence_ms)
        return cfg.silence_ms

    @staticmethod
    def _resample_to_int16(samples, source_rate: int, target_rate: int) -> bytes:
        import numpy as np

        mono = np.asarray(samples, dtype=np.float32).reshape(-1)
        if source_rate != target_rate:
            try:
                from scipy.signal import resample_poly

                from math import gcd

                divisor = gcd(source_rate, target_rate)
                mono = resample_poly(
                    mono,
                    target_rate // divisor,
                    source_rate // divisor,
                ).astype(np.float32, copy=False)
            except ImportError:
                output_length = max(1, round(len(mono) * target_rate / source_rate))
                old_x = np.linspace(0.0, 1.0, num=len(mono), endpoint=False)
                new_x = np.linspace(0.0, 1.0, num=output_length, endpoint=False)
                mono = np.interp(new_x, old_x, mono).astype(np.float32)
        mono = np.clip(mono, -1.0, 1.0)
        return (mono * 32767.0).astype("<i2").tobytes()

    def _capture_sync(self) -> bytes:
        try:
            import numpy as np
            import sounddevice as sd
        except ImportError as exc:
            raise LocalMicrophoneError(
                "Χρειάζονται τα πακέτα sounddevice και numpy για το PC microphone mode."
            ) from exc

        cfg = self.config
        blocksize = max(1, int(cfg.capture_rate * cfg.block_ms / 1000))
        pre_blocks = max(1, cfg.pre_buffer_ms // cfg.block_ms)
        max_blocks = max(1, int(cfg.max_seconds * 1000 / cfg.block_ms))
        pre_buffer: deque = deque(maxlen=pre_blocks)
        captured: list = []
        speaking = False
        silent_count = 0

        try:
            with sd.InputStream(
                device=cfg.device,
                samplerate=cfg.capture_rate,
                channels=cfg.channels,
                dtype="float32",
                blocksize=blocksize,
                latency="low",
            ) as stream:
                for _ in range(max_blocks):
                    # Playback can begin while this blocking capture loop is already
                    # running in a worker thread. Abort immediately so Nobi's own
                    # speech can never become part of the next Whisper utterance.
                    if self.playback_gate.blocked:
                        logger.debug("PC microphone capture cancelled: Nobi playback started")
                        return b""

                    data, overflowed = stream.read(blocksize)

                    # The gate may have closed while PortAudio was blocked in read().
                    if self.playback_gate.blocked:
                        logger.debug("PC microphone capture cancelled after read: Nobi playback started")
                        return b""

                    if overflowed:
                        logger.debug("PC microphone overflow")
                    block = np.asarray(data, dtype=np.float32)
                    if block.ndim == 2:
                        block = block.mean(axis=1)
                    rms = float(np.sqrt(np.mean(np.square(block)))) if block.size else 0.0

                    if not speaking:
                        pre_buffer.append(block.copy())
                        if rms >= cfg.speech_threshold:
                            speaking = True
                            captured.extend(pre_buffer)
                            pre_buffer.clear()
                        continue

                    captured.append(block.copy())
                    if rms < cfg.speech_threshold:
                        silent_count += 1
                        speech_seconds = len(captured) * cfg.block_ms / 1000.0
                        endpoint_ms = self._endpoint_silence_ms(speech_seconds)
                        silence_blocks = max(1, endpoint_ms // cfg.block_ms)
                        if silent_count >= silence_blocks:
                            logger.debug(
                                "Adaptive endpoint: speech={:.2f}s, silence={}ms",
                                speech_seconds,
                                endpoint_ms,
                            )
                            break
                    else:
                        silent_count = 0
        except Exception as exc:
            raise LocalMicrophoneError(f"Αποτυχία PC μικροφώνου: {exc}") from exc

        if not captured:
            return b""
        samples = np.concatenate(captured)
        return self._resample_to_int16(samples, cfg.capture_rate, cfg.target_rate)

    async def run(self) -> None:
        cfg = self.config
        logger.info(
            "PC microphone enabled: device={}, capture={}Hz, target={}Hz, threshold={:.4f}, adaptive={}, silence={}→{}→{}ms, max={:.0f}s",
            cfg.device,
            cfg.capture_rate,
            cfg.target_rate,
            cfg.speech_threshold,
            cfg.adaptive_listening,
            cfg.silence_ms,
            max(cfg.silence_ms, cfg.medium_silence_ms),
            max(cfg.silence_ms, cfg.long_silence_ms),
            cfg.max_seconds,
        )
        while self.running:
            await self.playback_gate.wait_until_open()
            if not self.running:
                return
            started = perf_counter()
            try:
                pcm = await asyncio.to_thread(self._capture_sync)
                if self.playback_gate.blocked:
                    logger.debug("Discarded PC microphone capture during Nobi playback")
                    continue
                if not pcm:
                    await asyncio.sleep(cfg.retry_delay)
                    continue
                duration = len(pcm) / float(cfg.target_rate * 2)
                logger.info(
                    "PC microphone utterance ready: bytes={}, audio={:.2f}s, capture={:.2f}s",
                    len(pcm),
                    duration,
                    perf_counter() - started,
                )
                await self.submit(pcm, cfg.target_rate, cfg.language)
            except LocalMicrophoneError as exc:
                logger.error("{}", exc)
                await asyncio.sleep(max(1.0, cfg.retry_delay))
