"""Configuration for the RobotOS Node client."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class NodeConfig:
    brain_host: str = os.getenv("ROBOTOS_BRAIN_HOST", "127.0.0.1")
    brain_port: int = int(os.getenv("ROBOTOS_BRAIN_PORT", "8765"))

    node_id: str = os.getenv("ROBOTOS_NODE_ID", "raspberry-pi-01")
    node_name: str = os.getenv(
        "ROBOTOS_NODE_NAME",
        "RobotOS Raspberry Node",
    )

    heartbeat_interval: float = 5.0
    reconnect_delay: float = 3.0
    handshake_timeout: float = 10.0
    log_level: str = "INFO"

    piper_executable: str = os.getenv("PIPER_EXECUTABLE", "piper")
    piper_model: Path = Path(
        os.getenv(
            "PIPER_MODEL",
            "/home/pi/robot/models/"
            "el_GR-rapunzelina-medium.onnx",
        )
    )
    audio_player: str = os.getenv("AUDIO_PLAYER", "aplay")

    @property
    def brain_uri(self) -> str:
        return f"ws://{self.brain_host}:{self.brain_port}"


CONFIG = NodeConfig()