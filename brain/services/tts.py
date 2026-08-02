"""High-quality local TTS backends for the Windows Brain.

Chatterbox runs in a persistent subprocess so its PyTorch/cuDNN runtime is
isolated from faster-whisper/CTranslate2 DLLs loaded by the Brain process.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Protocol
from uuid import uuid4

from loguru import logger

from shared.emotions import parse_emotion, VOICE_STYLES


class TTSError(RuntimeError):
    """Raised when a TTS backend cannot synthesize audio."""


class TTSBackend(Protocol):
    name: str

    async def synthesize(self, text: str, *, emotion: str | None = None) -> bytes: ...

    async def close(self) -> None: ...


def build_worker_environment(base: dict[str, str] | None = None) -> dict[str, str]:
    """Return an environment that prioritizes the PyTorch-bundled cuDNN DLLs."""

    env = dict(os.environ if base is None else base)
    separator = os.pathsep
    current_entries = [entry for entry in env.get("PATH", "").split(separator) if entry]

    # Old globally installed cuDNN 8 DLLs can be loaded before PyTorch cuDNN 9
    # on Windows. The worker does not need those legacy paths.
    clean_entries = [
        entry
        for entry in current_entries
        if "cuda\\v8.9.7\\bin" not in entry.lower()
        and "cudnn\\v8.9.7\\bin" not in entry.lower()
    ]

    torch_lib = Path(sys.prefix) / "Lib" / "site-packages" / "torch" / "lib"
    scripts = Path(sys.prefix) / "Scripts"
    preferred = [str(torch_lib), str(scripts)]
    if os.name == "nt":
        preferred.append(str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"))

    combined: list[str] = []
    for entry in [*preferred, *clean_entries]:
        if entry and entry not in combined:
            combined.append(entry)
    env["PATH"] = separator.join(combined)
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


class ChatterboxWorkerTTS:
    """Persistent Chatterbox worker isolated in a separate Python process."""

    name = "chatterbox"

    def __init__(
        self,
        *,
        device: str = "cuda",
        language_id: str = "el",
        reference_audio: str | None = None,
        startup_timeout: float = 180.0,
        synthesis_timeout: float = 180.0,
        worker_module: str = "brain.services.tts_worker",
    ) -> None:
        self.device = device
        self.language_id = language_id
        self.reference_audio = Path(reference_audio).expanduser() if reference_audio else None
        self.startup_timeout = startup_timeout
        self.synthesis_timeout = synthesis_timeout
        self.worker_module = worker_module
        self._process: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def _pump_stderr(self, stream: asyncio.StreamReader) -> None:
        while True:
            line = await stream.readline()
            if not line:
                return
            logger.info("TTS worker: {}", line.decode(errors="replace").rstrip())

    async def _start_worker(self) -> None:
        if self._process is not None and self._process.returncode is None:
            return

        command = [
            sys.executable,
            "-m",
            self.worker_module,
            "--device",
            self.device,
            "--language",
            self.language_id,
        ]
        if self.reference_audio:
            if not self.reference_audio.is_file():
                raise TTSError(f"Δεν βρέθηκε voice reference: {self.reference_audio}")
            command.extend(["--reference-audio", str(self.reference_audio)])

        logger.info("Starting isolated Chatterbox worker on {}", self.device)
        self._process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=build_worker_environment(),
        )
        assert self._process.stdout is not None
        assert self._process.stderr is not None
        self._stderr_task = asyncio.create_task(
            self._pump_stderr(self._process.stderr), name="chatterbox-worker-stderr"
        )

        try:
            raw = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=self.startup_timeout
            )
        except asyncio.TimeoutError as exc:
            await self._terminate_worker()
            raise TTSError("Το Chatterbox worker δεν ξεκίνησε εγκαίρως") from exc

        if not raw:
            code = await self._process.wait()
            await self._terminate_worker()
            raise TTSError(f"Το Chatterbox worker τερματίστηκε κατά την εκκίνηση (code={code})")

        try:
            response = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            await self._terminate_worker()
            raise TTSError("Μη έγκυρη απάντηση εκκίνησης από το Chatterbox worker") from exc
        if response.get("status") != "ready":
            await self._terminate_worker()
            raise TTSError(response.get("error", "Αποτυχία εκκίνησης Chatterbox worker"))
        logger.info("Chatterbox worker ready: pid={}", self._process.pid)

    async def _terminate_worker(self) -> None:
        process = self._process
        self._process = None
        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        if self._stderr_task is not None:
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except asyncio.CancelledError:
                pass
            self._stderr_task = None

    async def preload(self) -> None:
        """Start the persistent worker before the first request."""

        async with self._lock:
            await self._start_worker()

    async def synthesize(self, text: str, *, emotion: str | None = None) -> bytes:
        clean = text.strip()
        if not clean:
            raise TTSError("Δεν γίνεται σύνθεση κενού κειμένου")

        async with self._lock:
            await self._start_worker()
            assert self._process is not None
            assert self._process.stdin is not None
            assert self._process.stdout is not None

            request_id = str(uuid4())
            output_path = Path(tempfile.gettempdir()) / f"robotos-tts-{request_id}.wav"
            selected_emotion = parse_emotion(emotion)
            style = VOICE_STYLES[selected_emotion]
            request = {
                "id": request_id,
                "command": "synthesize",
                "text": clean,
                "output_path": str(output_path),
                "emotion": selected_emotion.value,
                "exaggeration": style.exaggeration,
                "cfg_weight": style.cfg_weight,
            }
            try:
                self._process.stdin.write((json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"))
                await self._process.stdin.drain()
                raw = await asyncio.wait_for(
                    self._process.stdout.readline(), timeout=self.synthesis_timeout
                )
                if not raw:
                    code = await self._process.wait()
                    self._process = None
                    raise TTSError(f"Το Chatterbox worker τερματίστηκε (code={code})")
                response = json.loads(raw.decode("utf-8"))
                if response.get("id") != request_id:
                    raise TTSError("Ασυμφωνία απάντησης από το Chatterbox worker")
                if response.get("status") != "ok":
                    raise TTSError(response.get("error", "Αποτυχία σύνθεσης Chatterbox"))
                if not output_path.is_file():
                    raise TTSError("Το Chatterbox worker δεν δημιούργησε WAV")
                return await asyncio.to_thread(output_path.read_bytes)
            except asyncio.TimeoutError as exc:
                await self._terminate_worker()
                raise TTSError("Η σύνθεση Chatterbox ξεπέρασε το χρονικό όριο") from exc
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                await self._terminate_worker()
                raise TTSError("Μη έγκυρη απάντηση από το Chatterbox worker") from exc
            finally:
                output_path.unlink(missing_ok=True)

    async def close(self) -> None:
        """Stop the persistent worker cleanly."""

        async with self._lock:
            if self._process is not None and self._process.returncode is None:
                assert self._process.stdin is not None
                try:
                    self._process.stdin.write(b'{"command":"shutdown"}\n')
                    await self._process.stdin.drain()
                    await asyncio.wait_for(self._process.wait(), timeout=10)
                except (BrokenPipeError, ConnectionError, asyncio.TimeoutError):
                    await self._terminate_worker()
                else:
                    self._process = None
            if self._stderr_task is not None:
                self._stderr_task.cancel()
                try:
                    await self._stderr_task
                except asyncio.CancelledError:
                    pass
                self._stderr_task = None


# Backwards-compatible public name used by BrainServer and external imports.
ChatterboxTTS = ChatterboxWorkerTTS
