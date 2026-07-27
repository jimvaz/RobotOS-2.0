"""Brain speech delivery service."""

from __future__ import annotations

from loguru import logger
from websockets.asyncio.server import ServerConnection

from brain.connection_manager import ConnectionManager
from shared.speech import SpeechPayload


class SpeechService:
    """Create and deliver SPEECH messages to connected RobotOS nodes."""

    def __init__(self, connections: ConnectionManager) -> None:
        self._connections = connections

    async def say(
        self,
        text: str,
        *,
        emotion: str | None = None,
        exclude: ServerConnection | None = None,
    ) -> int:
        """Broadcast speech and return the number of successful deliveries."""

        message = SpeechPayload(text=text, emotion=emotion).to_message()
        delivered = 0

        for websocket in self._connections.connections:
            if websocket is exclude:
                continue
            try:
                await websocket.send(message.to_json())
            except Exception:
                logger.exception("Failed to deliver speech to a connected node")
                await self._connections.disconnect(websocket)
            else:
                delivered += 1

        logger.info(
            "Speech dispatched: recipients={}, text={!r}",
            delivered,
            text.strip(),
        )
        return delivered
