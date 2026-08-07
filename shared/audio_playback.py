"""Wire payloads for streamed Brain-generated audio playback on a RobotOS Node."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from uuid import uuid4

from pydantic import BaseModel, Field

from shared.models import Message
from shared.protocol import MessageType


class AudioPlaybackModel(BaseModel):
    """Legacy single-message WAV payload."""

    audio_base64: str = Field(min_length=1)
    format: str = "wav"
    text: str = ""
    engine: str = "unknown"


@dataclass(frozen=True, slots=True)
class AudioPlaybackPayload:
    """Legacy payload retained for backwards compatibility."""

    audio: bytes
    format: str = "wav"
    text: str = ""
    engine: str = "unknown"

    def to_message(self) -> Message:
        return Message(
            type=MessageType.AUDIO_PLAYBACK,
            payload={
                "audio_base64": base64.b64encode(self.audio).decode("ascii"),
                "format": self.format,
                "text": self.text,
                "engine": self.engine,
            },
        )

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


class AudioPlaybackStartModel(BaseModel):
    stream_id: str = Field(min_length=1)
    speech_id: str = ""
    segment_index: int = Field(default=0, ge=0)
    segment_count: int = Field(default=1, gt=0)
    format: str = "wav"
    text: str = ""
    engine: str = "unknown"
    total_bytes: int = Field(ge=0)
    chunk_size: int = Field(gt=0)


class AudioPlaybackChunkModel(BaseModel):
    stream_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    audio_base64: str = Field(min_length=1)


class AudioPlaybackEndModel(BaseModel):
    stream_id: str = Field(min_length=1)
    speech_id: str = ""
    segment_index: int = Field(default=0, ge=0)
    segment_count: int = Field(default=1, gt=0)
    final_segment: bool = True
    chunks: int = Field(ge=0)
    total_bytes: int = Field(ge=0)


@dataclass(frozen=True, slots=True)
class AudioPlaybackStartPayload:
    stream_id: str
    total_bytes: int
    chunk_size: int
    speech_id: str = ""
    segment_index: int = 0
    segment_count: int = 1
    format: str = "wav"
    text: str = ""
    engine: str = "unknown"

    @classmethod
    def create(
        cls,
        *,
        total_bytes: int,
        chunk_size: int,
        format: str = "wav",
        text: str = "",
        engine: str = "unknown",
        speech_id: str = "",
        segment_index: int = 0,
        segment_count: int = 1,
    ) -> "AudioPlaybackStartPayload":
        return cls(
            stream_id=str(uuid4()),
            total_bytes=total_bytes,
            chunk_size=chunk_size,
            speech_id=speech_id,
            segment_index=segment_index,
            segment_count=segment_count,
            format=format,
            text=text,
            engine=engine,
        )

    def to_message(self) -> Message:
        return Message(type=MessageType.AUDIO_PLAYBACK_START, payload={
            "stream_id": self.stream_id,
            "speech_id": self.speech_id,
            "segment_index": self.segment_index,
            "segment_count": self.segment_count,
            "format": self.format,
            "text": self.text,
            "engine": self.engine,
            "total_bytes": self.total_bytes,
            "chunk_size": self.chunk_size,
        })

    @classmethod
    def from_message(cls, message: Message) -> "AudioPlaybackStartPayload":
        if message.type != MessageType.AUDIO_PLAYBACK_START:
            raise ValueError("Expected AUDIO_PLAYBACK_START message")
        model = AudioPlaybackStartModel.model_validate(message.payload)
        return cls(**model.model_dump())


@dataclass(frozen=True, slots=True)
class AudioPlaybackChunkPayload:
    stream_id: str
    sequence: int
    audio: bytes

    def to_message(self) -> Message:
        if not self.audio:
            raise ValueError("Audio chunk cannot be empty")
        return Message(type=MessageType.AUDIO_PLAYBACK_CHUNK, payload={
            "stream_id": self.stream_id,
            "sequence": self.sequence,
            "audio_base64": base64.b64encode(self.audio).decode("ascii"),
        })

    @classmethod
    def from_message(cls, message: Message) -> "AudioPlaybackChunkPayload":
        if message.type != MessageType.AUDIO_PLAYBACK_CHUNK:
            raise ValueError("Expected AUDIO_PLAYBACK_CHUNK message")
        model = AudioPlaybackChunkModel.model_validate(message.payload)
        try:
            audio = base64.b64decode(model.audio_base64, validate=True)
        except Exception as exc:
            raise ValueError("Invalid base64 audio chunk") from exc
        if not audio:
            raise ValueError("Empty audio chunk")
        return cls(stream_id=model.stream_id, sequence=model.sequence, audio=audio)


@dataclass(frozen=True, slots=True)
class AudioPlaybackEndPayload:
    stream_id: str
    chunks: int
    total_bytes: int
    speech_id: str = ""
    segment_index: int = 0
    segment_count: int = 1
    final_segment: bool = True

    def to_message(self) -> Message:
        return Message(type=MessageType.AUDIO_PLAYBACK_END, payload={
            "stream_id": self.stream_id,
            "chunks": self.chunks,
            "total_bytes": self.total_bytes,
            "speech_id": self.speech_id,
            "segment_index": self.segment_index,
            "segment_count": self.segment_count,
            "final_segment": self.final_segment,
        })

    @classmethod
    def from_message(cls, message: Message) -> "AudioPlaybackEndPayload":
        if message.type != MessageType.AUDIO_PLAYBACK_END:
            raise ValueError("Expected AUDIO_PLAYBACK_END message")
        model = AudioPlaybackEndModel.model_validate(message.payload)
        return cls(**model.model_dump())


class AudioPlaybackCancelModel(BaseModel):
    speech_id: str = Field(min_length=1)
    reason: str = "cancelled"


@dataclass(frozen=True, slots=True)
class AudioPlaybackCancelPayload:
    speech_id: str
    reason: str = "cancelled"

    def to_message(self) -> Message:
        return Message(
            type=MessageType.AUDIO_PLAYBACK_CANCEL,
            payload={"speech_id": self.speech_id, "reason": self.reason},
        )

    @classmethod
    def from_message(cls, message: Message) -> "AudioPlaybackCancelPayload":
        if message.type != MessageType.AUDIO_PLAYBACK_CANCEL:
            raise ValueError("Expected AUDIO_PLAYBACK_CANCEL message")
        model = AudioPlaybackCancelModel.model_validate(message.payload)
        return cls(**model.model_dump())


class AudioPlaybackFinishedModel(BaseModel):
    speech_id: str = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class AudioPlaybackFinishedPayload:
    """Node acknowledgement emitted only after the final sample has played."""
    speech_id: str

    def to_message(self) -> Message:
        return Message(type=MessageType.AUDIO_PLAYBACK_FINISHED, payload={"speech_id": self.speech_id})

    @classmethod
    def from_message(cls, message: Message) -> "AudioPlaybackFinishedPayload":
        if message.type != MessageType.AUDIO_PLAYBACK_FINISHED:
            raise ValueError("Expected AUDIO_PLAYBACK_FINISHED message")
        model = AudioPlaybackFinishedModel.model_validate(message.payload)
        return cls(speech_id=model.speech_id)
