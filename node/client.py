"""RobotOS Node WebSocket client."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from loguru import logger
from pydantic import ValidationError
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from node.config import CONFIG
from node.handlers import create_speech_handler
from node.router import NodeMessageRouter
from node.tts import PiperTTS, SpeechQueue
from shared.models import Message
from shared.protocol import MessageType
from shared.version import PROTOCOL_VERSION, ROBOTOS_VERSION


class NodeClient:
    """Connects the Raspberry Pi Node to the RobotOS Brain."""

    def __init__(self) -> None:
        self.running = True
        self.websocket: ClientConnection | None = None
        self.router = NodeMessageRouter()
        self.piper = PiperTTS(
            executable=CONFIG.piper_executable,
            model_path=CONFIG.piper_model,
            audio_player=CONFIG.audio_player,
        )
        self.speech_queue = SpeechQueue(self.piper)
        self.router.register(
            MessageType.SPEECH,
            create_speech_handler(self.speech_queue),
        )

    async def send_message(self, message: Message) -> None:
        """Send a validated RobotOS protocol message."""

        if self.websocket is None:
            raise RuntimeError("Node is not connected to the Brain")

        await self.websocket.send(message.to_json())

        logger.debug(
            "Message sent: type={}, id={}",
            message.type,
            message.id,
        )

    async def perform_handshake(self) -> None:
        """Send HELLO and wait for acceptance from the Brain."""

        hello = Message(
            type=MessageType.HELLO,
            payload={
                "node_id": CONFIG.node_id,
                "node_name": CONFIG.node_name,
                "robotos_version": ROBOTOS_VERSION,
                "protocol_version": PROTOCOL_VERSION,
                "capabilities": [],
            },
        )

        await self.send_message(hello)
        logger.info("HELLO sent to Brain")

        if self.websocket is None:
            raise RuntimeError("Connection disappeared during handshake")

        raw_response = await asyncio.wait_for(
            self.websocket.recv(),
            timeout=CONFIG.handshake_timeout,
        )

        response = Message.from_json(raw_response)

        if response.type != MessageType.HELLO:
            raise RuntimeError(
                f"Expected HELLO response, received {response.type}"
            )

        if response.payload.get("status") != "accepted":
            raise RuntimeError(
                f"Brain rejected the Node: {response.payload}"
            )

        logger.info(
            "Handshake completed: brain={}, version={}, protocol={}",
            response.payload.get("brain_name", "unknown"),
            response.payload.get("robotos_version", "unknown"),
            response.payload.get("protocol_version", "unknown"),
        )

    async def heartbeat_loop(self) -> None:
        """Send regular heartbeat messages to the Brain."""

        while self.running:
            await asyncio.sleep(CONFIG.heartbeat_interval)

            heartbeat = Message(
                type=MessageType.HEARTBEAT,
                payload={
                    "node_id": CONFIG.node_id,
                    "status": "online",
                },
            )

            await self.send_message(heartbeat)
            logger.info("Heartbeat sent")

    async def receive_loop(self) -> None:
        """Receive and process messages from the Brain."""

        if self.websocket is None:
            raise RuntimeError("Node is not connected to the Brain")

        async for raw_message in self.websocket:
            try:
                message = Message.from_json(raw_message)
            except ValidationError as exc:
                logger.warning("Invalid message received from Brain: {}", exc)
                continue

            if message.type == MessageType.HEARTBEAT:
                logger.info(
                    "Heartbeat acknowledged: reply_to={}",
                    message.payload.get("reply_to", "unknown"),
                )
                continue

            if message.type == MessageType.ERROR:
                logger.error(
                    "Brain error: code={}, message={}",
                    message.payload.get("code", "unknown"),
                    message.payload.get("message", "No description"),
                )
                continue

            await self.router.dispatch(message)

    async def run_connection(self) -> None:
        """Run one connection session."""

        logger.info("Connecting to {}", CONFIG.brain_uri)

        async with connect(
            CONFIG.brain_uri,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
        ) as websocket:
            self.websocket = websocket

            logger.info("Connected to RobotOS Brain")

            await self.perform_handshake()

            heartbeat_task = asyncio.create_task(
                self.heartbeat_loop(),
                name="node-heartbeat",
            )

            receive_task = asyncio.create_task(
                self.receive_loop(),
                name="node-receiver",
            )

            try:
                done, pending = await asyncio.wait(
                    {heartbeat_task, receive_task},
                    return_when=asyncio.FIRST_EXCEPTION,
                )

                for task in done:
                    exception = task.exception()
                    if exception is not None:
                        raise exception

            finally:
                heartbeat_task.cancel()
                receive_task.cancel()

                with suppress(asyncio.CancelledError):
                    await heartbeat_task

                with suppress(asyncio.CancelledError):
                    await receive_task

                self.websocket = None

    async def start(self) -> None:
        """Connect continuously and automatically reconnect after failure."""

        self.speech_queue.start()

        while self.running:
            try:
                await self.run_connection()

            except ConnectionClosed as exc:
                logger.warning(
                    "Brain connection closed: code={}, reason={}",
                    exc.code,
                    exc.reason or "none",
                )

            except ConnectionRefusedError:
                logger.warning(
                    "Brain is unavailable at {}",
                    CONFIG.brain_uri,
                )

            except asyncio.TimeoutError:
                logger.warning("Handshake with Brain timed out")

            except OSError as exc:
                logger.warning("Network connection failed: {}", exc)

            except Exception:
                logger.exception("Unexpected Node client error")

            if self.running:
                logger.info(
                    "Reconnecting in {} seconds...",
                    CONFIG.reconnect_delay,
                )
                await asyncio.sleep(CONFIG.reconnect_delay)

    async def shutdown(self) -> None:
        """Stop network activity and finish queued speech."""

        self.running = False
        await self.speech_queue.stop(drain=True)

    def stop(self) -> None:
        """Request a graceful Node shutdown."""

        self.running = False

    def run(self) -> None:
        """Start the Node client."""

        async def runner() -> None:
            try:
                await self.start()
            finally:
                await self.shutdown()

        try:
            asyncio.run(runner())
        except KeyboardInterrupt:
            self.stop()
            logger.info("RobotOS Node stopped by user")
