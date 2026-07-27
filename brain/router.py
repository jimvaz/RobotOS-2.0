"""Message routing for the RobotOS Brain."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from loguru import logger
from websockets.asyncio.server import ServerConnection

from shared.models import Message
from shared.protocol import MessageType

MessageHandler = Callable[[ServerConnection, Message], Awaitable[None]]


class MessageRouter:
    """Dispatch validated protocol messages to registered async handlers."""

    def __init__(self) -> None:
        self._handlers: dict[MessageType, MessageHandler] = {}

    def register(self, message_type: MessageType, handler: MessageHandler) -> None:
        """Register a handler for one message type.

        Replacing handlers implicitly can hide configuration mistakes, so a
        duplicate registration is rejected explicitly.
        """

        if message_type in self._handlers:
            raise ValueError(f"Handler already registered for {message_type.value}")
        self._handlers[message_type] = handler

    def unregister(self, message_type: MessageType) -> None:
        """Remove a handler if one is registered."""

        self._handlers.pop(message_type, None)

    def has_handler(self, message_type: MessageType) -> bool:
        """Return whether a handler is registered for the message type."""

        return message_type in self._handlers

    async def dispatch(
        self,
        websocket: ServerConnection,
        message: Message,
    ) -> bool:
        """Dispatch a message and return whether a handler was found."""

        message_type = MessageType(message.type)
        handler = self._handlers.get(message_type)

        if handler is None:
            logger.warning("No handler exists yet for message type: {}", message_type)
            return False

        await handler(websocket, message)
        return True
