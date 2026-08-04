import base64

import pytest

from brain.services.speech import SpeechService, split_for_fast_speech
from shared.models import Message
from shared.protocol import MessageType


class Connections:
    def __init__(self, sockets):
        self.connections = set(sockets)

    async def disconnect(self, websocket):
        self.connections.discard(websocket)


class Socket:
    def __init__(self):
        self.sent = []

    async def send(self, raw):
        self.sent.append(Message.from_json(raw))


class Backend:
    name = "chatterbox"

    async def synthesize(self, text):
        return b"RIFF-wave-data"


@pytest.mark.asyncio
async def test_speech_service_streams_brain_audio_in_chunks():
    socket = Socket()
    service = SpeechService(
        Connections([socket]), backend=Backend(), chunk_size=4
    )
    assert await service.say("Γεια") == 1

    assert socket.sent[0].type == MessageType.AUDIO_PLAYBACK_START
    assert socket.sent[-1].type == MessageType.AUDIO_PLAYBACK_END
    chunks = [
        message
        for message in socket.sent
        if message.type == MessageType.AUDIO_PLAYBACK_CHUNK
    ]
    rebuilt = b"".join(
        base64.b64decode(message.payload["audio_base64"]) for message in chunks
    )
    assert rebuilt == b"RIFF-wave-data"
    assert [message.payload["sequence"] for message in chunks] == list(range(len(chunks)))
    assert socket.sent[-1].payload["total_bytes"] == len(rebuilt)


@pytest.mark.asyncio
async def test_speech_service_large_audio_never_sends_large_frames():
    class LargeBackend:
        name = "chatterbox"

        async def synthesize(self, text):
            return b"x" * (10 * 1024 * 1024)

    socket = Socket()
    service = SpeechService(
        Connections([socket]), backend=LargeBackend(), chunk_size=48 * 1024
    )
    await service.say("Μεγάλη απάντηση")
    assert max(len(message.to_json()) for message in socket.sent) < 100_000


@pytest.mark.asyncio
async def test_speech_service_without_backend_sends_text():
    socket = Socket()
    service = SpeechService(Connections([socket]))
    await service.say("Γεια")
    assert socket.sent[0].type == MessageType.SPEECH


def test_fast_speech_split_preserves_natural_sentences():
    text = "Καλημέρα! Χαίρομαι που σε ακούω. Πώς μπορώ να βοηθήσω;"
    assert split_for_fast_speech(text) == [
        "Καλημέρα!",
        "Χαίρομαι που σε ακούω.",
        "Πώς μπορώ να βοηθήσω;",
    ]


@pytest.mark.asyncio
async def test_speech_service_synthesizes_and_dispatches_sentence_first():
    class TrackingBackend:
        name = "chatterbox"

        def __init__(self):
            self.calls = []

        async def synthesize(self, text, emotion=None):
            self.calls.append(text)
            return ("RIFF-" + text).encode("utf-8")

    backend = TrackingBackend()
    socket = Socket()
    service = SpeechService(Connections([socket]), backend=backend, chunk_size=4096)
    await service.say("Πρώτη πρόταση. Δεύτερη πρόταση!")

    assert backend.calls == ["Πρώτη πρόταση.", "Δεύτερη πρόταση!"]
    starts = [m for m in socket.sent if m.type == MessageType.AUDIO_PLAYBACK_START]
    ends = [m for m in socket.sent if m.type == MessageType.AUDIO_PLAYBACK_END]
    assert len(starts) == 2
    assert starts[0].payload["speech_id"] == starts[1].payload["speech_id"]
    assert starts[0].payload["segment_index"] == 0
    assert starts[1].payload["segment_index"] == 1
    assert ends[0].payload["final_segment"] is False
    assert ends[1].payload["final_segment"] is True
