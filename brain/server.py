"""RobotOS Brain WebSocket server."""

from __future__ import annotations

import asyncio

from loguru import logger
from pydantic import ValidationError
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from brain.config import CONFIG
from brain.connection_manager import ConnectionManager
from brain.handlers import create_speech_handler, handle_heartbeat, handle_hello
from brain.router import MessageRouter
from brain.services import SpeechService
from shared.models import Message
from shared.protocol import MessageType


class BrainServer:
    """Accept connections and delegate validated messages to the router."""

    def __init__(self, router: MessageRouter | None = None) -> None:
        self.connections = ConnectionManager()
        self.speech = SpeechService(self.connections)
        self.router = router or self._create_default_router()

    def _create_default_router(self) -> MessageRouter:
        """Build the standard Brain protocol routing table."""

        router = MessageRouter()
        router.register(MessageType.HELLO, handle_hello)
        router.register(MessageType.HEARTBEAT, handle_heartbeat)
        router.register(MessageType.SPEECH, create_speech_handler(self.speech))
        return router

    async def handle_client(self, websocket: ServerConnection) -> None:
        """Handle one connected RobotOS node."""

        remote_address = websocket.remote_address
        await self.connections.connect(websocket)
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
            await self.connections.disconnect(websocket)
            logger.info("Node disconnected: {}", remote_address)

    async def handle_message(
        self,
        websocket: ServerConnection,
        raw_message: str | bytes,
    ) -> None:
        """Validate an incoming protocol message and dispatch it."""

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

        logger.info("Message received: type={}, id={}", message.type, message.id)
        await self.router.dispatch(websocket, message)

    async def start(self) -> None:
        """Start the WebSocket server and wait indefinitely."""

        logger.info("Starting WebSocket server on ws://{}:{}", CONFIG.host, CONFIG.port)
        async with serve(self.handle_client, CONFIG.host, CONFIG.port):
            logger.info("Waiting for RobotOS nodes...")
            await asyncio.Future()

    def run(self) -> None:
        """Run the Brain server."""

        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            logger.info("Brain server stopped by user")
