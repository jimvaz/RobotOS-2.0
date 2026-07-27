"""Tests for the B1.5.1 speech event pipeline."""

from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
from pydantic import ValidationError
from websockets.asyncio.server import ServerConnection

from brain.connection_manager import ConnectionManager
from brain.handlers.speech import create_speech_handler
from brain.services import SpeechService
from node.router import NodeMessageRouter
from shared.models import Message
from shared.protocol import MessageType
from shared.speech import SpeechPayload


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, data: str) -> None:
        self.sent.append(data)


def server_connection(fake: FakeWebSocket) -> ServerConnection:
    return cast(ServerConnection, cast(Any, fake))


def test_speech_payload_builds_protocol_message() -> None:
    payload = SpeechPayload(text="  Καλησπέρα!  ", emotion=" happy ")

    message = payload.to_message()

    assert message.type == MessageType.SPEECH
    assert message.payload == {"text": "Καλησπέρα!", "emotion": "happy"}


def test_speech_payload_round_trip() -> None:
    original = SpeechPayload(text="Γεια σου")
    restored = SpeechPayload.from_message(
        Message.from_json(original.to_message().to_json())
    )

    assert restored == original


def test_speech_payload_rejects_blank_text() -> None:
    with pytest.raises(ValidationError):
        SpeechPayload(text="   ")


def test_speech_service_delivers_to_connected_nodes() -> None:
    manager = ConnectionManager()
    first = FakeWebSocket()
    second = FakeWebSocket()
    asyncio.run(manager.connect(server_connection(first)))
    asyncio.run(manager.connect(server_connection(second)))
    service = SpeechService(manager)

    delivered = asyncio.run(service.say("Καλημέρα"))

    assert delivered == 2
    assert SpeechPayload.from_message(Message.from_json(first.sent[0])).text == "Καλημέρα"
    assert SpeechPayload.from_message(Message.from_json(second.sent[0])).text == "Καλημέρα"


def test_speech_service_excludes_command_sender() -> None:
    manager = ConnectionManager()
    sender = FakeWebSocket()
    node = FakeWebSocket()
    sender_connection = server_connection(sender)
    asyncio.run(manager.connect(sender_connection))
    asyncio.run(manager.connect(server_connection(node)))
    service = SpeechService(manager)

    delivered = asyncio.run(service.say("Δοκιμή", exclude=sender_connection))

    assert delivered == 1
    assert sender.sent == []
    assert len(node.sent) == 1


def test_brain_speech_handler_forwards_valid_command() -> None:
    manager = ConnectionManager()
    sender = FakeWebSocket()
    node = FakeWebSocket()
    sender_connection = server_connection(sender)
    asyncio.run(manager.connect(sender_connection))
    asyncio.run(manager.connect(server_connection(node)))
    handler = create_speech_handler(SpeechService(manager))

    asyncio.run(
        handler(sender_connection, SpeechPayload(text="Έτοιμο").to_message())
    )

    received = SpeechPayload.from_message(Message.from_json(node.sent[0]))
    assert received.text == "Έτοιμο"
    assert sender.sent == []


def test_brain_speech_handler_replies_with_error_for_invalid_payload() -> None:
    manager = ConnectionManager()
    sender = FakeWebSocket()
    sender_connection = server_connection(sender)
    asyncio.run(manager.connect(sender_connection))
    handler = create_speech_handler(SpeechService(manager))
    message = Message(type=MessageType.SPEECH, payload={"text": "   "})

    asyncio.run(handler(sender_connection, message))

    response = Message.from_json(sender.sent[0])
    assert response.type == MessageType.ERROR
    assert response.payload["code"] == "invalid_speech"
    assert response.payload["reply_to"] == message.id


def test_node_router_dispatches_speech_message() -> None:
    router = NodeMessageRouter()
    received: list[str] = []

    async def handler(message: Message) -> None:
        received.append(SpeechPayload.from_message(message).text)

    router.register(MessageType.SPEECH, handler)

    handled = asyncio.run(
        router.dispatch(SpeechPayload(text="Καλησπέρα").to_message())
    )

    assert handled is True
    assert received == ["Καλησπέρα"]
