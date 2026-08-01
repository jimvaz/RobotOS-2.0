"""Wire payload for interrupting active robot speech."""
from __future__ import annotations

from dataclasses import dataclass

from shared.models import Message
from shared.protocol import MessageType


@dataclass(frozen=True, slots=True)
class SpeechInterruptPayload:
    reason: str = "user_speech"

    def to_message(self) -> Message:
        return Message(type=MessageType.SPEECH_INTERRUPT, payload={"reason": self.reason})

    @classmethod
    def from_message(cls, message: Message) -> "SpeechInterruptPayload":
        if message.type != MessageType.SPEECH_INTERRUPT:
            raise ValueError("Expected SPEECH_INTERRUPT message")
        return cls(reason=str(message.payload.get("reason", "user_speech")))
