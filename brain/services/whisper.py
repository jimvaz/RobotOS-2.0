"""Whisper transcription service with lazy faster-whisper loading."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


class WhisperError(RuntimeError):
    """Raised when Whisper cannot be loaded or audio cannot be transcribed."""


@dataclass(frozen=True, slots=True)
class WhisperResult:
    text: str
    language: str
    duration_seconds: float


class WhisperService:
    """Transcribe signed 16-bit little-endian mono PCM audio."""

    def __init__(
        self,
        model_name: str = "turbo",
        device: str = "cuda",
        compute_type: str = "float16",
        model: Any | None = None,
        beam_size: int = 1,
        best_of: int = 1,
        vad_filter: bool = False,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self._model = model
        self.beam_size = beam_size
        self.best_of = best_of
        self.vad_filter = vad_filter

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise WhisperError(
                "Το faster-whisper δεν είναι εγκατεστημένο στον Brain."
            ) from exc
        self._model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.compute_type,
        )
        return self._model

    def _transcribe_sync(
        self,
        pcm: bytes,
        sample_rate: int,
        language: str,
    ) -> WhisperResult:
        if not pcm:
            return WhisperResult(text="", language=language, duration_seconds=0.0)
        if len(pcm) % 2:
            raise WhisperError("Το PCM payload πρέπει να περιέχει πλήρη int16 samples.")
        try:
            import numpy as np
        except ImportError as exc:
            raise WhisperError("Το numpy δεν είναι εγκατεστημένο στον Brain.") from exc

        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        if sample_rate != 16000:
            raise WhisperError("Το B1.6 υποστηρίζει PCM στα 16000 Hz.")

        model = self._load_model()
        segments, info = model.transcribe(
            samples,
            language=language,
            beam_size=self.beam_size,
            best_of=self.best_of,
            vad_filter=self.vad_filter,
            condition_on_previous_text=False,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        detected_language = getattr(info, "language", language) or language
        duration = len(samples) / sample_rate
        return WhisperResult(text=text, language=detected_language, duration_seconds=duration)

    async def preload(self) -> None:
        """Load the model before the first utterance."""

        await asyncio.to_thread(self._load_model)

    async def transcribe(
        self,
        pcm: bytes,
        sample_rate: int = 16000,
        language: str = "el",
    ) -> WhisperResult:
        return await asyncio.to_thread(
            self._transcribe_sync,
            pcm,
            sample_rate,
            language,
        )
