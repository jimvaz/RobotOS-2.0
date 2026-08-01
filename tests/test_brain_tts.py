import pytest
from brain.services.speech import SpeechService
from shared.models import Message
from shared.protocol import MessageType

class Connections:
    def __init__(self, sockets): self.connections=set(sockets)
    async def disconnect(self, websocket): self.connections.discard(websocket)
class Socket:
    def __init__(self): self.sent=[]
    async def send(self, raw): self.sent.append(Message.from_json(raw))
class Backend:
    name="chatterbox"
    async def synthesize(self, text): return b"RIFF-wave"

@pytest.mark.asyncio
async def test_speech_service_sends_brain_audio():
    socket=Socket(); service=SpeechService(Connections([socket]), backend=Backend())
    assert await service.say("Γεια") == 1
    assert socket.sent[0].type == MessageType.AUDIO_PLAYBACK
    assert socket.sent[0].payload["engine"] == "chatterbox"

@pytest.mark.asyncio
async def test_speech_service_without_backend_sends_text():
    socket=Socket(); service=SpeechService(Connections([socket]))
    await service.say("Γεια")
    assert socket.sent[0].type == MessageType.SPEECH
