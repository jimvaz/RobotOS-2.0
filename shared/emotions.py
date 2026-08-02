"""Shared RobotOS speaking emotions and Chatterbox style profiles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Emotion(StrEnum):
    """Small, stable set of voice styles used across RobotOS."""

    NEUTRAL = "neutral"
    FRIENDLY = "friendly"
    THINKING = "thinking"
    CURIOUS = "curious"
    EXCITED = "excited"
    FUNNY = "funny"


@dataclass(frozen=True, slots=True)
class VoiceStyle:
    """Chatterbox parameters for one emotional delivery style."""

    exaggeration: float
    cfg_weight: float


VOICE_STYLES: dict[Emotion, VoiceStyle] = {
    Emotion.NEUTRAL: VoiceStyle(exaggeration=0.64, cfg_weight=0.34),
    Emotion.FRIENDLY: VoiceStyle(exaggeration=0.68, cfg_weight=0.32),
    Emotion.THINKING: VoiceStyle(exaggeration=0.56, cfg_weight=0.38),
    Emotion.CURIOUS: VoiceStyle(exaggeration=0.70, cfg_weight=0.30),
    Emotion.EXCITED: VoiceStyle(exaggeration=0.74, cfg_weight=0.28),
    Emotion.FUNNY: VoiceStyle(exaggeration=0.72, cfg_weight=0.29),
}


def parse_emotion(value: str | Emotion | None) -> Emotion:
    """Return a known emotion, falling back safely to neutral."""

    if isinstance(value, Emotion):
        return value
    if isinstance(value, str):
        try:
            return Emotion(value.strip().lower())
        except ValueError:
            pass
    return Emotion.NEUTRAL
