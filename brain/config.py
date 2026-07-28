"""Configuration for the RobotOS Brain server."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ServerConfig:
    host: str = os.getenv("ROBOTOS_BRAIN_BIND_HOST", "0.0.0.0")
    port: int = int(os.getenv("ROBOTOS_BRAIN_PORT", "8765"))
    log_level: str = os.getenv("ROBOTOS_LOG_LEVEL", "INFO")

    whisper_model: str = os.getenv("ROBOTOS_WHISPER_MODEL", "turbo")
    whisper_device: str = os.getenv("ROBOTOS_WHISPER_DEVICE", "cuda")
    whisper_compute_type: str = os.getenv(
        "ROBOTOS_WHISPER_COMPUTE_TYPE",
        "float16",
    )
    max_audio_seconds: int = int(os.getenv("ROBOTOS_MAX_AUDIO_SECONDS", "60"))


CONFIG = ServerConfig()
