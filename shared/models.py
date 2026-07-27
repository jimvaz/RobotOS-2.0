"""Validated message models for RobotOS protocol v1."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .protocol import MessageType
from .version import PROTOCOL_VERSION


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Message(BaseModel):
    """Base wire message exchanged between RobotOS Brain and Node."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    version: int = PROTOCOL_VERSION
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(default_factory=utc_now_iso)
    type: MessageType
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: int) -> int:
        if value != PROTOCOL_VERSION:
            raise ValueError(
                f"Unsupported protocol version {value}; expected {PROTOCOL_VERSION}"
            )
        return value

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str | bytes) -> "Message":
        return cls.model_validate_json(raw)
