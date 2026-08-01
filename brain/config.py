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
    max_history: int = int(os.getenv("ROBOTOS_MAX_HISTORY", "10"))

    tts_engine: str = os.getenv("ROBOTOS_TTS_ENGINE", "piper").strip().lower()
    chatterbox_device: str = os.getenv("ROBOTOS_CHATTERBOX_DEVICE", "cuda")
    chatterbox_language: str = os.getenv("ROBOTOS_CHATTERBOX_LANGUAGE", "el")
    chatterbox_reference_audio: str | None = os.getenv("ROBOTOS_CHATTERBOX_REFERENCE_AUDIO")
    chatterbox_startup_timeout: float = float(os.getenv("ROBOTOS_CHATTERBOX_STARTUP_TIMEOUT", "180"))
    chatterbox_synthesis_timeout: float = float(os.getenv("ROBOTOS_CHATTERBOX_SYNTHESIS_TIMEOUT", "180"))
    tts_fallback_to_node: bool = os.getenv("ROBOTOS_TTS_FALLBACK", "1").strip().lower() in {"1", "true", "yes", "on"}
    transcript_dedup_seconds: float = float(
        os.getenv("ROBOTOS_TRANSCRIPT_DEDUP_SECONDS", "3")
    )
    transcript_similarity_threshold: float = float(
        os.getenv("ROBOTOS_TRANSCRIPT_SIMILARITY_THRESHOLD", "0.92")
    )
    conversation_log_path: str = os.getenv(
        "ROBOTOS_CONVERSATION_LOG", "logs/conversations.jsonl"
    )

    system_prompt: str = os.getenv(
        "ROBOTOS_SYSTEM_PROMPT",
        (
            "Είσαι το RobotOS, ένα φιλικό ελληνόφωνο ρομπότ-βοηθός. "
            "Απαντάς αποκλειστικά στα ελληνικά και λαμβάνεις υπόψη το προηγούμενο "
            "ιστορικό της συζήτησης. Δίνεις σύντομες, φυσικές και ακριβείς απαντήσεις "
            "κατάλληλες για εκφώνηση. Δεν χρησιμοποιείς markdown, λίστες ή emoji, "
            "δεν επαναλαμβάνεις την ερώτηση και δεν επινοείς πληροφορίες όταν δεν γνωρίζεις."
        ),
    )


CONFIG = ServerConfig()
