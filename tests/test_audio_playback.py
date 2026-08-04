import pytest

from node.handlers.audio_playback import create_audio_stream_handlers
from shared.audio_playback import (
    AudioPlaybackCancelPayload,
    AudioPlaybackChunkPayload,
    AudioPlaybackEndPayload,
    AudioPlaybackPayload,
    AudioPlaybackStartPayload,
)
from shared.protocol import MessageType


def test_audio_playback_round_trip():
    payload = AudioPlaybackPayload(b"RIFF-test", text="γεια", engine="chatterbox")
    message = payload.to_message()
    assert message.type == MessageType.AUDIO_PLAYBACK
    restored = AudioPlaybackPayload.from_message(message)
    assert restored.audio == b"RIFF-test"
    assert restored.text == "γεια"
    assert restored.engine == "chatterbox"


def test_audio_playback_rejects_invalid_base64():
    message = AudioPlaybackPayload(b"x").to_message()
    message.payload["audio_base64"] = "%%%"
    with pytest.raises(ValueError):
        AudioPlaybackPayload.from_message(message)


def test_stream_payload_round_trip():
    start = AudioPlaybackStartPayload.create(
        total_bytes=9,
        chunk_size=4,
        text="γεια",
        engine="chatterbox",
    )
    restored_start = AudioPlaybackStartPayload.from_message(start.to_message())
    assert restored_start.stream_id == start.stream_id
    assert restored_start.total_bytes == 9

    chunk = AudioPlaybackChunkPayload(start.stream_id, 0, b"RIFF")
    restored_chunk = AudioPlaybackChunkPayload.from_message(chunk.to_message())
    assert restored_chunk.audio == b"RIFF"
    assert restored_chunk.sequence == 0

    end = AudioPlaybackEndPayload(start.stream_id, chunks=3, total_bytes=9)
    restored_end = AudioPlaybackEndPayload.from_message(end.to_message())
    assert restored_end.chunks == 3


class FakeStreamingQueue:
    def __init__(self):
        self.calls = []

    async def begin_stream(self, stream_id, **kwargs):
        self.calls.append(("start", stream_id, kwargs))

    async def write_stream_chunk(self, stream_id, sequence, audio):
        self.calls.append(("chunk", stream_id, sequence, audio))

    async def end_stream(self, stream_id, **kwargs):
        self.calls.append(("end", stream_id, kwargs))

    async def abort_stream(self, reason="aborted"):
        self.calls.append(("abort", reason))


@pytest.mark.asyncio
async def test_stream_handlers_forward_ordered_payloads():
    queue = FakeStreamingQueue()
    handle_start, handle_chunk, handle_end, handle_cancel = create_audio_stream_handlers(queue)
    start = AudioPlaybackStartPayload.create(total_bytes=4, chunk_size=4)

    await handle_start(start.to_message())
    await handle_chunk(AudioPlaybackChunkPayload(start.stream_id, 0, b"RIFF").to_message())
    await handle_end(AudioPlaybackEndPayload(start.stream_id, 1, 4).to_message())

    assert [call[0] for call in queue.calls] == ["start", "chunk", "end"]


@pytest.mark.asyncio
async def test_stream_cancel_finishes_sentence_sequence():
    queue = FakeStreamingQueue()

    async def finish_speech(speech_id, reason="finished"):
        queue.calls.append(("finish", speech_id, reason))

    queue.finish_speech = finish_speech
    _, _, _, handle_cancel = create_audio_stream_handlers(queue)
    await handle_cancel(AudioPlaybackCancelPayload("speech-1", "tts failed").to_message())
    assert queue.calls == [("finish", "speech-1", "tts failed")]
