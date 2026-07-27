"""Common internal events used by Brain and Node."""

from enum import Enum


class EventType(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    MESSAGE_RECEIVED = "message_received"
    HEARTBEAT_RECEIVED = "heartbeat_received"
    SPEECH_RECEIVED = "speech_received"
    ERROR = "error"
