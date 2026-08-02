"""Configuration for the RobotOS Brain server."""

from __future__ import annotations

import os
from dataclasses import dataclass

from brain.persona import CHARACTER_SYSTEM_PROMPT


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
    max_audio_seconds: int = int(os.getenv("ROBOTOS_MAX_AUDIO_SECONDS", "20"))
    whisper_beam_size: int = int(os.getenv("ROBOTOS_WHISPER_BEAM_SIZE", "1"))
    whisper_best_of: int = int(os.getenv("ROBOTOS_WHISPER_BEST_OF", "1"))
    whisper_vad_filter: bool = os.getenv("ROBOTOS_WHISPER_VAD_FILTER", "0").strip().lower() in {"1", "true", "yes", "on"}
    preload_models: bool = os.getenv("ROBOTOS_PRELOAD_MODELS", "1").strip().lower() in {"1", "true", "yes", "on"}

    ollama_model: str = os.getenv("ROBOTOS_OLLAMA_MODEL", "robot-greek")
    ollama_url: str = os.getenv("ROBOTOS_OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_timeout_seconds: float = float(
        os.getenv("ROBOTOS_OLLAMA_TIMEOUT_SECONDS", "120")
    )
    max_history: int = int(os.getenv("ROBOTOS_MAX_HISTORY", "8"))
    ollama_num_predict: int = int(os.getenv("ROBOTOS_OLLAMA_NUM_PREDICT", "80"))
    ollama_num_ctx: int = int(os.getenv("ROBOTOS_OLLAMA_NUM_CTX", "4096"))

    tts_engine: str = os.getenv("ROBOTOS_TTS_ENGINE", "piper").strip().lower()
    chatterbox_device: str = os.getenv("ROBOTOS_CHATTERBOX_DEVICE", "cuda")
    chatterbox_language: str = os.getenv("ROBOTOS_CHATTERBOX_LANGUAGE", "el")
    chatterbox_reference_audio: str | None = os.getenv("ROBOTOS_CHATTERBOX_REFERENCE_AUDIO")
    chatterbox_startup_timeout: float = float(os.getenv("ROBOTOS_CHATTERBOX_STARTUP_TIMEOUT", "180"))
    chatterbox_synthesis_timeout: float = float(os.getenv("ROBOTOS_CHATTERBOX_SYNTHESIS_TIMEOUT", "180"))
    tts_fallback_to_node: bool = os.getenv("ROBOTOS_TTS_FALLBACK", "1").strip().lower() in {"1", "true", "yes", "on"}
    emotion_engine_enabled: bool = os.getenv("ROBOTOS_EMOTION_ENGINE", "1").strip().lower() in {"1", "true", "yes", "on"}
    audio_playback_chunk_size: int = int(os.getenv("ROBOTOS_AUDIO_CHUNK_SIZE", str(48 * 1024)))
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
        CHARACTER_SYSTEM_PROMPT,
    )


CONFIG = ServerConfig()
