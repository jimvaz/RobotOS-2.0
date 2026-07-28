"""Piper text-to-speech service."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from loguru import logger


class PiperError(RuntimeError):
    """Raised when Piper synthesis or audio playback fails."""


class PiperTTS:
    """Generate speech with Piper and play it through the Node speakers."""

    def __init__(
        self,
        executable: str,
        model_path: Path,
        audio_player: str = "aplay",
    ) -> None:
        self.executable = executable
        self.model_path = model_path
        self.audio_player = audio_player
        self._speech_lock = asyncio.Lock()

    @staticmethod
    def _command_exists(command: str) -> bool:
        path = Path(command).expanduser()
        return path.is_file() if path.parent != Path(".") else shutil.which(command) is not None

    def validate(self) -> None:
        """Check Piper, the voice model, and the audio player."""

        if not self._command_exists(self.executable):
            raise PiperError(f"Δεν βρέθηκε το Piper executable: {self.executable}")

        if not self.model_path.expanduser().is_file():
            raise PiperError(f"Δεν βρέθηκε το μοντέλο Piper: {self.model_path}")

        config_path = Path(f"{self.model_path}.json")
        if not config_path.is_file():
            logger.warning("Δεν βρέθηκε το συνοδευτικό αρχείο μοντέλου: {}", config_path)

        if not self._command_exists(self.audio_player):
            raise PiperError(f"Δεν βρέθηκε το audio player: {self.audio_player}")

    async def speak(self, text: str) -> None:
        """Synthesize and play one text without overlapping other speech."""

        clean_text = text.strip()
        if not clean_text:
            logger.warning("Αγνοήθηκε κενό κείμενο ομιλίας")
            return

        async with self._speech_lock:
            self.validate()
            logger.info("Piper synthesis started: {!r}", clean_text)
            temporary_path: Path | None = None

            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporary_file:
                    temporary_path = Path(temporary_file.name)

                await self._synthesize(clean_text, temporary_path)
                await self._play(temporary_path)
                logger.info("Speech playback completed")
            finally:
                if temporary_path and temporary_path.exists():
                    temporary_path.unlink(missing_ok=True)

    async def _synthesize(self, text: str, output_path: Path) -> None:
        """Generate a WAV file with Piper."""

        try:
            process = await asyncio.create_subprocess_exec(
                self.executable,
                "--model",
                str(self.model_path),
                "--output_file",
                str(output_path),
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

    async def _play(self, audio_path: Path) -> None:
        """Play a WAV file through the Raspberry Pi audio output."""

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
