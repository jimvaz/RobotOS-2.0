"""Validated audio and transcript payloads for RobotOS protocol v1."""

from __future__ import annotations

import base64
import binascii
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import Message
from .protocol import MessageType


class AudioStartPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=128)
    sample_rate: int = Field(default=16000, ge=8000, le=48000)
    channels: int = Field(default=1, ge=1, le=2)
    sample_width: int = Field(default=2, ge=1, le=4)
    language: str = Field(default="el", min_length=2, max_length=16)

    @field_validator("session_id", "language")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    def to_message(self) -> Message:
        return Message(type=MessageType.AUDIO_START, payload=self.model_dump())

    @classmethod
    def from_message(cls, message: Message) -> "AudioStartPayload":
        if message.type != MessageType.AUDIO_START:
            raise ValueError("Expected AUDIO_START message")
        return cls.model_validate(message.payload)


class AudioChunkPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=128)
    sequence: int = Field(ge=0)
    data: str = Field(min_length=1)

    @field_validator("session_id")
    @classmethod
    def strip_session_id(cls, value: str) -> str:
        return value.strip()

    def decode(self) -> bytes:
        try:
            return base64.b64decode(self.data, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Audio chunk is not valid base64") from exc

    @classmethod
    def from_bytes(cls, session_id: str, sequence: int, data: bytes) -> "AudioChunkPayload":
        if not data:
            raise ValueError("Audio chunk cannot be empty")
        return cls(
            session_id=session_id,
            sequence=sequence,
            data=base64.b64encode(data).decode("ascii"),
        )

    def to_message(self) -> Message:
        return Message(type=MessageType.AUDIO_CHUNK, payload=self.model_dump())

    @classmethod
    def from_message(cls, message: Message) -> "AudioChunkPayload":
        if message.type != MessageType.AUDIO_CHUNK:
            raise ValueError("Expected AUDIO_CHUNK message")
        return cls.model_validate(message.payload)


class AudioEndPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=128)
    chunk_count: int = Field(ge=0)

    @field_validator("session_id")
    @classmethod
    def strip_session_id(cls, value: str) -> str:
        return value.strip()

    def to_message(self) -> Message:
        return Message(type=MessageType.AUDIO_END, payload=self.model_dump())

    @classmethod
    def from_message(cls, message: Message) -> "AudioEndPayload":
        if message.type != MessageType.AUDIO_END:
            raise ValueError("Expected AUDIO_END message")
        return cls.model_validate(message.payload)


class TranscriptPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=128)
    text: str
    language: str = "el"
    duration_seconds: float = Field(default=0.0, ge=0.0)

    @field_validator("session_id", "text", "language")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    def to_message(self) -> Message:
        return Message(type=MessageType.TRANSCRIPT, payload=self.model_dump())

    @classmethod
    def from_message(cls, message: Message) -> "TranscriptPayload":
        if message.type != MessageType.TRANSCRIPT:
            raise ValueError("Expected TRANSCRIPT message")
        return cls.model_validate(message.payload)
