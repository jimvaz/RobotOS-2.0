"""Queue and play WAV audio synthesized by the Brain."""
from __future__ import annotations
import asyncio
import tempfile
from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path
from loguru import logger

Hook = Callable[[], Awaitable[None]]

class AudioPlaybackQueue:
    def __init__(self, player: str = "aplay", *, on_start: Hook | None = None, on_end: Hook | None = None) -> None:
        self.player = player
        self.on_start = on_start
        self.on_end = on_end
        self.queue: asyncio.Queue[tuple[bytes,str,str]] = asyncio.Queue()
        self.worker: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self.worker is None or self.worker.done():
            self.worker = asyncio.create_task(self._run(), name="node-audio-playback")

    async def enqueue(self, audio: bytes, text: str = "", engine: str = "unknown") -> None:
        self.start(); await self.queue.put((audio,text,engine))

    async def stop(self) -> None:
        await self.queue.join()
        if self.worker:
            self.worker.cancel()
            with suppress(asyncio.CancelledError): await self.worker

    async def _run(self) -> None:
        while True:
            audio,text,engine = await self.queue.get()
            path: Path | None = None
            try:
                if self.on_start: await self.on_start()
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(audio); path=Path(f.name)
                logger.info("[AUDIO] started: engine={}, text={!r}", engine, text)
                proc=await asyncio.create_subprocess_exec(self.player,"-q",str(path),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
                _,err=await proc.communicate()
                if proc.returncode: raise RuntimeError(err.decode(errors="replace"))
                logger.info("[AUDIO] finished")
            except Exception:
                logger.exception("Brain audio playback failed")
            finally:
                if path: path.unlink(missing_ok=True)
                if self.on_end: await self.on_end()
                self.queue.task_done()
