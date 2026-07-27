"""Tests for Brain message routing and default handlers."""

from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
from websockets.asyncio.server import ServerConnection

from brain.handlers import handle_heartbeat, handle_hello
from brain.router import MessageRouter
from shared.models import Message
from shared.protocol import MessageType
from shared.version import BRAIN_NAME, PROTOCOL_VERSION, ROBOTOS_VERSION


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, data: str) -> None:
        self.sent.append(data)


def websocket() -> tuple[ServerConnection, FakeWebSocket]:
    fake = FakeWebSocket()
    return cast(ServerConnection, cast(Any, fake)), fake


def test_router_dispatches_registered_handler() -> None:
    router = MessageRouter()
    connection, _ = websocket()
    received: list[str] = []

    async def handler(_websocket: ServerConnection, message: Message) -> None:
        received.append(message.id)

    message = Message(type=MessageType.STATUS)
    router.register(MessageType.STATUS, handler)

    handled = asyncio.run(router.dispatch(connection, message))

    assert handled is True
    assert received == [message.id]


def test_router_returns_false_for_unknown_handler() -> None:
    router = MessageRouter()
    connection, _ = websocket()

    handled = asyncio.run(
        router.dispatch(connection, Message(type=MessageType.SPEECH))
    )

    assert handled is False


def test_router_rejects_duplicate_registration() -> None:
    router = MessageRouter()

    async def handler(_websocket: ServerConnection, _message: Message) -> None:
        return None

    router.register(MessageType.HELLO, handler)

    with pytest.raises(ValueError, match="already registered"):
        router.register(MessageType.HELLO, handler)


def test_hello_handler_sends_acceptance_response() -> None:
    connection, fake = websocket()
    message = Message(
        type=MessageType.HELLO,
        payload={"node_name": "robot-node"},
    )

    asyncio.run(handle_hello(connection, message))

    response = Message.from_json(fake.sent[0])
    assert response.type == MessageType.HELLO
    assert response.payload == {
        "status": "accepted",
        "brain_name": BRAIN_NAME,
        "robotos_version": ROBOTOS_VERSION,
        "protocol_version": PROTOCOL_VERSION,
    }


def test_heartbeat_handler_replies_to_original_message() -> None:
    connection, fake = websocket()
    message = Message(type=MessageType.HEARTBEAT)

    asyncio.run(handle_heartbeat(connection, message))

    response = Message.from_json(fake.sent[0])
    assert response.type == MessageType.HEARTBEAT
    assert response.payload == {"status": "alive", "reply_to": message.id}
