"""Default protocol handlers for the RobotOS Brain."""

from brain.handlers.audio import create_audio_handlers
from brain.handlers.heartbeat import handle_heartbeat
from brain.handlers.hello import handle_hello
from brain.handlers.speech import create_speech_handler

__all__ = [
    "create_audio_handlers",
    "create_speech_handler",
    "handle_heartbeat",
    "handle_hello",
]
