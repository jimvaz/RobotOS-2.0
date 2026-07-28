"""Configuration for the RobotOS Node client."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class NodeConfig:
    brain_host: str = os.getenv("ROBOTOS_BRAIN_HOST", "127.0.0.1")
    brain_port: int = int(os.getenv("ROBOTOS_BRAIN_PORT", "8765"))

    node_id: str = os.getenv("ROBOTOS_NODE_ID", "raspberry-pi-01")
    node_name: str = os.getenv("ROBOTOS_NODE_NAME", "RobotOS Raspberry Node")

    heartbeat_interval: float = 5.0
    reconnect_delay: float = 3.0
    handshake_timeout: float = 10.0
    log_level: str = os.getenv("ROBOTOS_LOG_LEVEL", "INFO")

    piper_executable: str = os.getenv("PIPER_EXECUTABLE", "piper")
    piper_model: Path = Path(
        os.getenv(
            "PIPER_MODEL",
            "/home/pi/RobotOS-2.0/models/piper/el_GR-rapunzelina-medium.onnx",
        )
    )
    audio_player: str = os.getenv("AUDIO_PLAYER", "aplay")

    microphone_enabled: bool = _env_bool("ROBOTOS_MICROPHONE_ENABLED", False)
    microphone_sample_rate: int = int(os.getenv("ROBOTOS_MIC_SAMPLE_RATE", "16000"))
    microphone_threshold: float = float(os.getenv("ROBOTOS_MIC_THRESHOLD", "0.015"))
    microphone_silence_ms: int = int(os.getenv("ROBOTOS_MIC_SILENCE_MS", "700"))
    microphone_pre_buffer_ms: int = int(os.getenv("ROBOTOS_MIC_PRE_BUFFER_MS", "300"))
    microphone_max_seconds: float = float(os.getenv("ROBOTOS_MIC_MAX_SECONDS", "15"))
    microphone_retry_delay: float = float(os.getenv("ROBOTOS_MIC_RETRY_DELAY", "1"))
    language: str = os.getenv("ROBOTOS_LANGUAGE", "el")

    @property
    def brain_uri(self) -> str:
        return f"ws://{self.brain_host}:{self.brain_port}"


CONFIG = NodeConfig()
