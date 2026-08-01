"""Brain speech delivery with optional local high-quality synthesis."""
from __future__ import annotations
from loguru import logger
from websockets.asyncio.server import ServerConnection
from brain.connection_manager import ConnectionManager
from brain.services.tts import TTSBackend, TTSError
from shared.audio_playback import AudioPlaybackPayload
from shared.speech import SpeechPayload

class SpeechService:
    def __init__(self, connections: ConnectionManager, *, backend: TTSBackend | None = None, fallback_to_node: bool = True) -> None:
        self._connections = connections
        self._backend = backend
        self._fallback_to_node = fallback_to_node

    async def say(self, text: str, *, emotion: str | None = None, exclude: ServerConnection | None = None) -> int:
        clean = text.strip()
        message = None
        if self._backend is not None:
            try:
                audio = await self._backend.synthesize(clean)
                message = AudioPlaybackPayload(audio=audio, text=clean, engine=self._backend.name).to_message()
                logger.info("High-quality TTS generated: engine={}, bytes={}", self._backend.name, len(audio))
            except TTSError as exc:
                logger.error("High-quality TTS failed: {}", exc)
                if not self._fallback_to_node:
                    raise
        if message is None:
            message = SpeechPayload(text=clean, emotion=emotion).to_message()
            logger.info("Using Node Piper fallback")
        delivered = 0
        for websocket in self._connections.connections:
            if websocket is exclude: continue
            try: await websocket.send(message.to_json())
            except Exception:
                logger.exception("Failed to deliver speech")
                await self._connections.disconnect(websocket)
            else: delivered += 1
        logger.info("Speech dispatched: recipients={}, text={!r}", delivered, clean)
        return delivered
    async def close(self) -> None:
        """Release resources held by the configured TTS backend."""
        if self._backend is not None:
            close = getattr(self._backend, "close", None)
            if close is not None:
                await close()

