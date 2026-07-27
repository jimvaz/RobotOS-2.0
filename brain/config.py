"""Configuration for the RobotOS Brain server."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8765
    log_level: str = "INFO"


CONFIG = ServerConfig()