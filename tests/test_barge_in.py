import asyncio

import pytest

from brain.handlers.interrupt import create_speech_interrupt_handler
from shared.barge_in import SpeechInterruptPayload
from shared.protocol import MessageType


def test_speech_interrupt_payload_round_trip():
    payload = SpeechInterruptPayload(reason="user_speech")
    message = payload.to_message()
    assert message.type == MessageType.SPEECH_INTERRUPT
    assert SpeechInterruptPayload.from_message(message).reason == "user_speech"


class FakeSpeech:
    def __init__(self):
        self.cancelled = []

    def cancel_for(self, websocket):
        self.cancelled.append(websocket)


@pytest.mark.asyncio
async def test_brain_interrupt_handler_marks_connection_cancelled():
    speech = FakeSpeech()
    websocket = object()
    handler = create_speech_interrupt_handler(speech)
    await handler(websocket, SpeechInterruptPayload().to_message())
    assert speech.cancelled == [websocket]


@pytest.mark.asyncio
async def test_audio_playback_interrupt_stops_active_stream(monkeypatch):
    from node.tts.audio_player import AudioPlaybackQueue, _ActiveStream

    class Process:
        returncode = None
        stdin = None
        def terminate(self):
            self.returncode = -15
        async def wait(self):
            return self.returncode

    queue = AudioPlaybackQueue()
    process = Process()
    queue._stream = _ActiveStream("s1", process, 0, 0, 10, "", "test")
    await queue.interrupt("test")
    assert queue._stream is None
