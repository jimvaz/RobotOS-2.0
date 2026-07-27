import json

import pytest
from pydantic import ValidationError

from shared.models import Message
from shared.protocol import MessageType
from shared.version import PROTOCOL_VERSION


def test_message_defaults_are_unique() -> None:
    first = Message(type=MessageType.HELLO)
    second = Message(type=MessageType.HELLO)

    assert first.id != second.id
    assert first.payload == {}
    assert first.version == PROTOCOL_VERSION
    assert first.timestamp.endswith("Z")


def test_message_round_trip() -> None:
    original = Message(
        type=MessageType.SPEECH,
        payload={"text": "Καλημέρα!", "emotion": "happy"},
    )

    restored = Message.from_json(original.to_json())

    assert restored == original


def test_serialized_message_is_valid_json() -> None:
    message = Message(type=MessageType.STATUS, payload={"state": "ready"})
    parsed = json.loads(message.to_json())

    assert parsed["type"] == "status"
    assert parsed["payload"]["state"] == "ready"


def test_rejects_wrong_protocol_version() -> None:
    with pytest.raises(ValidationError):
        Message(version=99, type=MessageType.HELLO)


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Message(type=MessageType.HELLO, unexpected=True)
