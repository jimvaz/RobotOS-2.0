"""RobotOS Brain WebSocket server."""

from __future__ import annotations

import asyncio

from loguru import logger
from pydantic import ValidationError
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from brain.config import CONFIG
from shared.models import Message
from shared.protocol import MessageType
from shared.version import BRAIN_NAME, PROTOCOL_VERSION, ROBOTOS_VERSION


class BrainServer:
    """Accepts and handles connections from RobotOS nodes."""

    def __init__(self) -> None:
        self.clients: set[ServerConnection] = set()

    async def handle_client(self, websocket: ServerConnection) -> None:
        """Handle one connected RobotOS node."""

        remote_address = websocket.remote_address
        self.clients.add(websocket)

        logger.info("Node connected: {}", remote_address)

        try:
            async for raw_message in websocket:
                await self.handle_message(websocket, raw_message)

        except ConnectionClosed as exc:
            logger.warning(
                "Node connection closed: code={}, reason={}",
                exc.code,
                exc.reason or "none",
            )

        except Exception:
            logger.exception("Unexpected client error")

        finally:
            self.clients.discard(websocket)
            logger.info("Node disconnected: {}", remote_address)

    async def handle_message(
        self,
        websocket: ServerConnection,
        raw_message: str | bytes,
    ) -> None:
        """Validate and route an incoming protocol message."""

        try:
            message = Message.from_json(raw_message)

        except ValidationError as exc:
            logger.warning("Invalid protocol message: {}", exc)

            error_message = Message(
                type=MessageType.ERROR,
                payload={
                    "code": "invalid_message",
                    "message": "The received message is invalid.",
                },
            )

            await websocket.send(error_message.to_json())
            return

        logger.info(
            "Message received: type={}, id={}",
            message.type,
            message.id,
        )

        if message.type == MessageType.HELLO:
            await self.handle_hello(websocket, message)
            return

        if message.type == MessageType.HEARTBEAT:
            await self.handle_heartbeat(websocket, message)
            return

        logger.warning("No handler exists yet for message type: {}", message.type)

    async def handle_hello(
        self,
        websocket: ServerConnection,
        message: Message,
    ) -> None:
        """Respond to the initial node handshake."""

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

    async def handle_heartbeat(
        self,
        websocket: ServerConnection,
        message: Message,
    ) -> None:
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

    async def start(self) -> None:
        """Start the WebSocket server and wait indefinitely."""

        logger.info(
            "Starting WebSocket server on ws://{}:{}",
            CONFIG.host,
            CONFIG.port,
        )

        async with serve(
            self.handle_client,
            CONFIG.host,
            CONFIG.port,
        ):
            logger.info("Waiting for RobotOS nodes...")
            await asyncio.Future()

    def run(self) -> None:
        """Run the Brain server."""

        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            logger.info("Brain server stopped by user")