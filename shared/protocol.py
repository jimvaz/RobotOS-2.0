"""Message types supported by RobotOS protocol v1."""

from enum import Enum


class MessageType(str, Enum):
    HELLO = "hello"
    HEARTBEAT = "heartbeat"
    STATUS = "status"
    SPEECH = "speech"
    ACTION = "action"
    EVENT = "event"
    ERROR = "error"
