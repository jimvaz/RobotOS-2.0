import pytest
from shared.audio_playback import AudioPlaybackPayload
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
