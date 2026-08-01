"""Message types supported by RobotOS protocol v1."""

from enum import Enum


class MessageType(str, Enum):
    HELLO = "hello"
    HEARTBEAT = "heartbeat"
    STATUS = "status"
    SPEECH = "speech"
    AUDIO_START = "audio_start"
    AUDIO_CHUNK = "audio_chunk"
    AUDIO_END = "audio_end"
    AUDIO_PLAYBACK = "audio_playback"
    TRANSCRIPT = "transcript"
    ACTION = "action"
    EVENT = "event"
    ERROR = "error"
