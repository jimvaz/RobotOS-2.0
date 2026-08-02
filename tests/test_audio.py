"""Tests for the B1.6 audio streaming and transcription pipeline."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, cast

import pytest
from websockets.asyncio.server import ServerConnection

from brain.handlers.audio import create_audio_handlers
from brain.services.audio_buffer import AudioBufferService, AudioSessionError
from brain.services.whisper import WhisperResult
from node.audio import AudioStreamer
from shared.audio import AudioChunkPayload, AudioEndPayload, AudioStartPayload, TranscriptPayload
from shared.models import Message
from shared.protocol import MessageType


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, data: str) -> None:
        self.sent.append(data)


def connection(fake: FakeWebSocket) -> ServerConnection:
    return cast(ServerConnection, cast(Any, fake))


@dataclass
class FakeWhisper:
    text: str = "Καλημέρα RobotOS"

    async def transcribe(self, pcm: bytes, sample_rate: int, language: str) -> WhisperResult:
        assert pcm == b"\x01\x02\x03\x04"
        assert sample_rate == 16000
        assert language == "el"
        return WhisperResult(self.text, "el", 0.5)


def test_audio_chunk_round_trip() -> None:
    payload = AudioChunkPayload.from_bytes("session-1", 3, b"\x00\x01\xff")
    restored = AudioChunkPayload.from_message(Message.from_json(payload.to_message().to_json()))

    assert restored.session_id == "session-1"
    assert restored.sequence == 3
    assert restored.decode() == b"\x00\x01\xff"


def test_audio_buffer_assembles_ordered_pcm() -> None:
    buffers = AudioBufferService(max_audio_bytes=100)
    owner = object()
    start = AudioStartPayload(session_id="s1")
    buffers.start(owner, start)
    buffers.append(owner, AudioChunkPayload.from_bytes("s1", 0, b"ab"))
    buffers.append(owner, AudioChunkPayload.from_bytes("s1", 1, b"cd"))

    metadata, pcm = buffers.finish(owner, AudioEndPayload(session_id="s1", chunk_count=2))

    assert metadata == start
    assert pcm == b"abcd"


def test_audio_buffer_rejects_out_of_order_chunk() -> None:
    buffers = AudioBufferService()
    owner = object()
    buffers.start(owner, AudioStartPayload(session_id="s1"))

    with pytest.raises(AudioSessionError, match="expected 0"):
        buffers.append(owner, AudioChunkPayload.from_bytes("s1", 1, b"bad"))


def test_audio_streamer_sends_start_chunks_and_end() -> None:
    sent: list[Message] = []

    async def sender(message: Message) -> None:
        sent.append(message)

    async def scenario() -> str:
        streamer = AudioStreamer(sender, chunk_bytes=3)
        return await streamer.stream(b"abcdefg", session_id="fixed")

    session_id = asyncio.run(scenario())

    assert session_id == "fixed"
    assert [message.type for message in sent] == [
        MessageType.AUDIO_START,
        MessageType.AUDIO_CHUNK,
        MessageType.AUDIO_CHUNK,
        MessageType.AUDIO_CHUNK,
        MessageType.AUDIO_END,
    ]
    assert b"".join(AudioChunkPayload.from_message(message).decode() for message in sent[1:-1]) == b"abcdefg"
    assert AudioEndPayload.from_message(sent[-1]).chunk_count == 3


def test_brain_audio_handlers_return_transcript() -> None:
    fake = FakeWebSocket()
    websocket = connection(fake)
    handlers = create_audio_handlers(AudioBufferService(), cast(Any, FakeWhisper()))
    handle_start, handle_chunk, handle_end = handlers

    async def scenario() -> None:
        await handle_start(websocket, AudioStartPayload(session_id="s1").to_message())
        await handle_chunk(
            websocket,
            AudioChunkPayload.from_bytes("s1", 0, b"\x01\x02\x03\x04").to_message(),
        )
        await handle_end(websocket, AudioEndPayload(session_id="s1", chunk_count=1).to_message())

    asyncio.run(scenario())

    transcript = TranscriptPayload.from_message(Message.from_json(fake.sent[-1]))
    assert transcript.text == "Καλημέρα RobotOS"
    assert transcript.session_id == "s1"


def test_brain_audio_handler_reports_unknown_session() -> None:
    fake = FakeWebSocket()
    websocket = connection(fake)
    _, handle_chunk, _ = create_audio_handlers(AudioBufferService(), cast(Any, FakeWhisper()))

    asyncio.run(
        handle_chunk(
            websocket,
            AudioChunkPayload.from_bytes("missing", 0, b"data").to_message(),
        )
    )

    response = Message.from_json(fake.sent[0])
    assert response.type == MessageType.ERROR
    assert response.payload["code"] == "invalid_audio_chunk"

@dataclass
class FakeLLMResult:
    text: str = "Καλημέρα! Πώς μπορώ να βοηθήσω;"
    model: str = "robot-greek"


class FakeLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(
        self, prompt: str, history: list[dict[str, str]] | None = None
    ) -> FakeLLMResult:
        self.prompts.append(prompt)
        return FakeLLMResult()


class FakeSpeech:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def say(self, text: str, **kwargs: Any) -> int:
        self.messages.append(text)
        return 1


def test_audio_pipeline_sends_transcript_to_llm_and_speech() -> None:
    fake = FakeWebSocket()
    websocket = connection(fake)
    llm = FakeLLM()
    speech = FakeSpeech()
    handlers = create_audio_handlers(
        AudioBufferService(),
        cast(Any, FakeWhisper()),
        cast(Any, llm),
        cast(Any, speech),
    )
    handle_start, handle_chunk, handle_end = handlers

    async def scenario() -> None:
        await handle_start(websocket, AudioStartPayload(session_id="s1").to_message())
        await handle_chunk(
            websocket,
            AudioChunkPayload.from_bytes("s1", 0, b"\x01\x02\x03\x04").to_message(),
        )
        await handle_end(websocket, AudioEndPayload(session_id="s1", chunk_count=1).to_message())

    asyncio.run(scenario())

    assert llm.prompts == ["Καλημέρα RobotOS"]
    assert speech.messages == ["Καλημέρα! Πώς μπορώ να βοηθήσω;"]
    transcript = TranscriptPayload.from_message(Message.from_json(fake.sent[-1]))
    assert transcript.text == "Καλημέρα RobotOS"


def test_audio_recorder_pause_and_resume_state() -> None:
    from node.audio import AudioRecorder

    recorder = AudioRecorder(sounddevice=object())

    assert recorder.paused is False
    recorder.pause()
    assert recorder.paused is True
    assert asyncio.run(recorder.record_utterance()) == b""
    recorder.resume()
    assert recorder.paused is False


def test_audio_recorder_waits_until_resumed() -> None:
    from node.audio import AudioRecorder

    async def scenario() -> bool:
        recorder = AudioRecorder(sounddevice=object())
        recorder.pause()

        async def resume_soon() -> None:
            await asyncio.sleep(0.01)
            recorder.resume()

        task = asyncio.create_task(resume_soon())
        await recorder.wait_until_resumed(poll_seconds=0.001)
        await task
        return recorder.paused

    assert asyncio.run(scenario()) is False


def test_low_latency_recorder_defaults() -> None:
    from node.audio import RecorderConfig

    config = RecorderConfig()
    assert config.silence_ms == 700  # library default remains backwards compatible
    assert config.pre_buffer_ms == 300
    assert config.max_utterance_seconds == 15.0


def test_audio_recorder_pause_invalidates_generation() -> None:
    from node.audio import AudioRecorder

    recorder = AudioRecorder(sounddevice=object())
    before = recorder.generation
    recorder.pause()
    assert recorder.generation > before
    paused_generation = recorder.generation
    recorder.resume()
    assert recorder.generation > paused_generation
