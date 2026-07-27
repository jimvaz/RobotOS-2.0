"""Default protocol handlers for the RobotOS Brain."""

from brain.handlers.heartbeat import handle_heartbeat
from brain.handlers.hello import handle_hello

__all__ = ["handle_heartbeat", "handle_hello"]
