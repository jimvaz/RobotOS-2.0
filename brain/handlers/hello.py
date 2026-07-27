"""HELLO handshake handler."""

from __future__ import annotations

from loguru import logger
from websockets.asyncio.server import ServerConnection

from shared.models import Message
from shared.protocol import MessageType
from shared.version import BRAIN_NAME, PROTOCOL_VERSION, ROBOTOS_VERSION


async def handle_hello(websocket: ServerConnection, message: Message) -> None:
    """Accept the initial node handshake."""

    node_name = message.payload.get("node_name", "unknown-node")
    logger.info("HELLO received from {}", node_name)

    response = Message(
        type=MessageType.HELLO,
        payload={
            "status": "accepted",
            "brain_name": BRAIN_NAME,
            "robotos_version": ROBOTOS_VERSION,
            "protocol_version": PROTOCOL_VERSION,
        },
    )

    await websocket.send(response.to_json())
    logger.info("HELLO response sent to {}", node_name)
