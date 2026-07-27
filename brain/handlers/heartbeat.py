"""HEARTBEAT handler."""

from __future__ import annotations

from loguru import logger
from websockets.asyncio.server import ServerConnection

from shared.models import Message
from shared.protocol import MessageType


async def handle_heartbeat(websocket: ServerConnection, message: Message) -> None:
    """Acknowledge a node heartbeat."""

    response = Message(
        type=MessageType.HEARTBEAT,
        payload={
            "status": "alive",
            "reply_to": message.id,
        },
    )

    await websocket.send(response.to_json())
    logger.debug("Heartbeat acknowledged")
