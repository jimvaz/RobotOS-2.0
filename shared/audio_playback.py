"""Wire payload for Brain-generated WAV playback on a RobotOS Node."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from pydantic import BaseModel, Field
from shared.models import Message
from shared.protocol import MessageType


class AudioPlaybackModel(BaseModel):
    audio_base64: str = Field(min_length=1)
    format: str = "wav"
    text: str = ""
    engine: str = "unknown"


@dataclass(frozen=True, slots=True)
class AudioPlaybackPayload:
    audio: bytes
    format: str = "wav"
    text: str = ""
    engine: str = "unknown"

    def to_message(self) -> Message:
        return Message(type=MessageType.AUDIO_PLAYBACK, payload={
            "audio_base64": base64.b64encode(self.audio).decode("ascii"),
            "format": self.format,
            "text": self.text,
            "engine": self.engine,
        })

    @classmethod
    def from_message(cls, message: Message) -> "AudioPlaybackPayload":
        if message.type != MessageType.AUDIO_PLAYBACK:
            raise ValueError("Expected AUDIO_PLAYBACK message")
        model = AudioPlaybackModel.model_validate(message.payload)
        try:
            audio = base64.b64decode(model.audio_base64, validate=True)
        except Exception as exc:
            raise ValueError("Invalid base64 audio payload") from exc
        if not audio:
            raise ValueError("Empty audio payload")
        return cls(audio=audio, format=model.format, text=model.text, engine=model.engine)
