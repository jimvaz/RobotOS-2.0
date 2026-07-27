"""Message routing for the RobotOS Node."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from loguru import logger

from shared.models import Message
from shared.protocol import MessageType

NodeMessageHandler = Callable[[Message], Awaitable[None]]


class NodeMessageRouter:
    """Dispatch validated Brain messages to registered Node handlers."""

    def __init__(self) -> None:
        self._handlers: dict[MessageType, NodeMessageHandler] = {}

    def register(self, message_type: MessageType, handler: NodeMessageHandler) -> None:
        if message_type in self._handlers:
            raise ValueError(f"Handler already registered for {message_type.value}")
        self._handlers[message_type] = handler

    async def dispatch(self, message: Message) -> bool:
        message_type = MessageType(message.type)
        handler = self._handlers.get(message_type)
        if handler is None:
            logger.info(
                "Message received from Brain: type={}, payload={}",
                message.type,
                message.payload,
            )
            return False
        await handler(message)
        return True
