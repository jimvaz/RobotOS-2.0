"""Piper text-to-speech service with optional SoX post-processing."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from node.tts.voice_engine import VoiceStyle


class PiperError(RuntimeError):
    """Raised when Piper synthesis or audio playback fails."""


class PiperTTS:
    """Generate speech with Piper and play it through the Node speakers."""

    def __init__(
        self,
        executable: str,
        model_path: Path,
        audio_player: str = "aplay",
        *,
        sox_executable: str = "sox",
        postprocess_enabled: bool = True,
    ) -> None:
        self.executable = executable
        self.model_path = model_path
        self.audio_player = audio_player
        self.sox_executable = sox_executable
        self.postprocess_enabled = postprocess_enabled
        self._speech_lock = asyncio.Lock()
        self._warned_missing_sox = False

    @staticmethod
    def _command_exists(command: str) -> bool:
        path = Path(command).expanduser()
        return path.is_file() if path.parent != Path(".") else shutil.which(command) is not None

    def validate(self) -> None:
        if not self._command_exists(self.executable):
            raise PiperError(f"Δεν βρέθηκε το Piper executable: {self.executable}")
        if not self.model_path.expanduser().is_file():
            raise PiperError(f"Δεν βρέθηκε το μοντέλο Piper: {self.model_path}")
        config_path = Path(f"{self.model_path}.json")
        if not config_path.is_file():
            logger.warning("Δεν βρέθηκε το συνοδευτικό αρχείο μοντέλου: {}", config_path)
        if not self._command_exists(self.audio_player):
            raise PiperError(f"Δεν βρέθηκε το audio player: {self.audio_player}")

    async def speak(self, text: str, *, style: VoiceStyle | None = None) -> None:
        clean_text = text.strip()
        if not clean_text:
            logger.warning("Αγνοήθηκε κενό κείμενο ομιλίας")
            return

        async with self._speech_lock:
            self.validate()
            logger.info("Piper synthesis started: {!r}", clean_text)
            raw_path: Path | None = None
            processed_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    raw_path = Path(tmp.name)
                await self._synthesize(clean_text, raw_path, style)
                playback_path = raw_path
                if style is not None and self.postprocess_enabled:
                    processed_path = raw_path.with_name(f"{raw_path.stem}-voice.wav")
                    if await self._postprocess(raw_path, processed_path, style):
                        playback_path = processed_path
                await self._play(playback_path)
                logger.info("Speech playback completed")
            finally:
                for path in (raw_path, processed_path):
                    if path and path.exists():
                        path.unlink(missing_ok=True)

    async def _synthesize(self, text: str, output_path: Path, style: VoiceStyle | None) -> None:
        command = [
            self.executable,
            "--model", str(self.model_path),
            "--output_file", str(output_path),
        ]
        if style is not None:
            command.extend([
                "--length_scale", str(style.length_scale),
                "--noise_scale", str(style.noise_scale),
                "--noise_w", str(style.noise_w),
                "--sentence_silence", str(style.sentence_silence),
            ])
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise PiperError(f"Δεν ήταν δυνατή η εκκίνηση του Piper: {exc}") from exc

        stdout, stderr = await process.communicate(input=text.encode("utf-8"))
        if process.returncode != 0:
            error = stderr.decode("utf-8", errors="replace").strip()
            raise PiperError(f"Η δημιουργία φωνής απέτυχε: {error or process.returncode}")
        if stdout:
            logger.debug("Piper output: {}", stdout.decode("utf-8", errors="replace").strip())
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise PiperError("Το Piper δεν δημιούργησε έγκυρο αρχείο WAV")

    async def _postprocess(self, input_path: Path, output_path: Path, style: VoiceStyle) -> bool:
        if not self._command_exists(self.sox_executable):
            if not self._warned_missing_sox:
                logger.warning("SoX not found; voice post-processing disabled")
                self._warned_missing_sox = True
            return False

        command = [self.sox_executable, str(input_path), str(output_path)]
        if style.pitch_cents:
            command.extend(["pitch", str(style.pitch_cents)])
        if abs(style.tempo - 1.0) > 0.001:
            command.extend(["tempo", "-s", str(style.tempo)])
        if abs(style.gain_db) > 0.001:
            command.extend(["gain", str(style.gain_db)])

        if len(command) == 3:
            return False
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            logger.warning("Voice post-processing could not start: {}", exc)
            return False
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.warning(
                "Voice post-processing failed; using raw Piper audio: {}",
                stderr.decode("utf-8", errors="replace").strip() or process.returncode,
            )
            return False
        return output_path.is_file() and output_path.stat().st_size > 0

    async def _play(self, audio_path: Path) -> None:
        try:
            process = await asyncio.create_subprocess_exec(
                self.audio_player,
                "-q",
                str(audio_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise PiperError(f"Δεν ήταν δυνατή η εκκίνηση του audio player: {exc}") from exc
        _, stderr = await process.communicate()
        if process.returncode != 0:
            error = stderr.decode("utf-8", errors="replace").strip()
            raise PiperError(f"Η αναπαραγωγή ήχου απέτυχε: {error or process.returncode}")
