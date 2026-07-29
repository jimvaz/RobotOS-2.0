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

    ollama_model: str = os.getenv("ROBOTOS_OLLAMA_MODEL", "robot-greek")
    ollama_url: str = os.getenv("ROBOTOS_OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_timeout_seconds: float = float(
        os.getenv("ROBOTOS_OLLAMA_TIMEOUT_SECONDS", "120")
    )
    system_prompt: str = os.getenv(
        "ROBOTOS_SYSTEM_PROMPT",
        (
            "Είσαι το RobotOS, ένα φιλικό ρομπότ-βοηθός. "
            "Απαντάς αποκλειστικά στα ελληνικά, σύντομα, καθαρά και ευγενικά. "
            "Οι απαντήσεις σου θα εκφωνούνται, επομένως απόφυγε markdown, "
            "λίστες, emoji και περιττές επαναλήψεις."
        ),
    )


CONFIG = ServerConfig()
