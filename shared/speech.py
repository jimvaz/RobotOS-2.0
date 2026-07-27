"""Shared speech payload validation for RobotOS protocol v1."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared.models import Message
from shared.protocol import MessageType


class SpeechPayload(BaseModel):
    """Validated payload carried by a SPEECH protocol message."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=4000)
    emotion: str | None = Field(default=None, max_length=64)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Speech text cannot be blank")
        return text

    @field_validator("emotion")
    @classmethod
    def normalize_emotion(cls, value: str | None) -> str | None:
        if value is None:
            return None
        emotion = value.strip()
        return emotion or None

    def to_message(self) -> Message:
        """Build a wire-level SPEECH message from this payload."""

        return Message(
            type=MessageType.SPEECH,
            payload=self.model_dump(exclude_none=True),
        )

    @classmethod
    def from_message(cls, message: Message) -> "SpeechPayload":
        """Validate and extract a speech payload from a protocol message."""

        if MessageType(message.type) is not MessageType.SPEECH:
            raise ValueError(f"Expected speech message, received {message.type}")
        return cls.model_validate(message.payload)
