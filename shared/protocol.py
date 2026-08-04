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
    AUDIO_PLAYBACK_START = "audio_playback_start"
    AUDIO_PLAYBACK_CHUNK = "audio_playback_chunk"
    AUDIO_PLAYBACK_END = "audio_playback_end"
    AUDIO_PLAYBACK_CANCEL = "audio_playback_cancel"
    SPEECH_INTERRUPT = "speech_interrupt"
    TRANSCRIPT = "transcript"
    ACTION = "action"
    EVENT = "event"
    ERROR = "error"
