from shared.protocol import MessageType


def test_protocol_values_are_stable() -> None:
    assert MessageType.HELLO.value == "hello"
    assert MessageType.HEARTBEAT.value == "heartbeat"
    assert MessageType.SPEECH.value == "speech"
