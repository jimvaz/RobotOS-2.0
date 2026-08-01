"""Default protocol handlers for the RobotOS Brain."""

from brain.handlers.audio import create_audio_handlers
from brain.handlers.heartbeat import handle_heartbeat
from brain.handlers.hello import handle_hello
from brain.handlers.interrupt import create_speech_interrupt_handler
from brain.handlers.speech import create_speech_handler

__all__ = [
    "create_audio_handlers",
    "create_speech_handler",
    "create_speech_interrupt_handler",
    "handle_heartbeat",
    "handle_hello",
]
