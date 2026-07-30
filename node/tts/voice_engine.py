"""Expressive voice profiles layered on top of Piper TTS."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from loguru import logger

from node.tts.piper import PiperTTS


@dataclass(frozen=True, slots=True)
class VoiceStyle:
    """Parameters controlling Piper prosody and optional post-processing."""

    name: str
    length_scale: float = 1.0
    noise_scale: float = 0.667
    noise_w: float = 0.8
    sentence_silence: float = 0.18
    pitch_cents: int = 0
    tempo: float = 1.0
    gain_db: float = 0.0


VOICE_PROFILES: dict[str, VoiceStyle] = {
    "classic": VoiceStyle(name="classic"),
    "cartoon": VoiceStyle(
        name="cartoon",
        length_scale=0.92,
        noise_scale=0.72,
        noise_w=0.82,
        sentence_silence=0.16,
        pitch_cents=180,
        tempo=1.06,
        gain_db=0.5,
    ),
    "energetic": VoiceStyle(
        name="energetic",
        length_scale=0.86,
        noise_scale=0.75,
        noise_w=0.86,
        sentence_silence=0.12,
        pitch_cents=120,
        tempo=1.10,
        gain_db=0.8,
    ),
    "kid": VoiceStyle(
        name="kid",
        length_scale=0.90,
        noise_scale=0.74,
        noise_w=0.84,
        sentence_silence=0.14,
        pitch_cents=280,
        tempo=1.08,
        gain_db=0.3,
    ),
    "calm": VoiceStyle(
        name="calm",
        length_scale=1.08,
        noise_scale=0.62,
        noise_w=0.74,
        sentence_silence=0.24,
        pitch_cents=-40,
        tempo=0.96,
        gain_db=-0.5,
    ),
}


class VoiceEngine:
    """Select an expressive style and delegate synthesis to Piper."""

    def __init__(
        self,
        piper: PiperTTS,
        *,
        profile: str = "cartoon",
        auto_expression: bool = True,
        pitch_override: int | None = None,
        tempo_override: float | None = None,
        gain_override: float | None = None,
    ) -> None:
        normalized = profile.strip().lower()
        if normalized not in VOICE_PROFILES:
            logger.warning("Unknown voice profile {!r}; using cartoon", profile)
            normalized = "cartoon"
        self.piper = piper
        self.profile = normalized
        self.auto_expression = auto_expression
        self.pitch_override = pitch_override
        self.tempo_override = tempo_override
        self.gain_override = gain_override

    @staticmethod
    def infer_emotion(text: str) -> str:
        """Infer a lightweight speaking style from Greek response text."""

        normalized = re.sub(r"\s+", " ", text.strip().lower())
        if any(word in normalized for word in ("συγγνώμη", "λυπάμαι", "δυστυχώς")):
            return "calm"
        if any(word in normalized for word in ("χαχα", "αστείο", "πλάκα")):
            return "playful"
        if normalized.startswith(("γεια", "καλημέρα", "καλησπέρα", "καλώς")):
            return "happy"
        if "!" in text:
            return "energetic"
        if text.rstrip().endswith("?"):
            return "curious"
        return "neutral"

    def resolve_style(self, text: str, emotion: str | None = None) -> VoiceStyle:
        """Resolve the configured profile plus a small expressive variation."""

        base = VOICE_PROFILES[self.profile]
        mood = (emotion or (self.infer_emotion(text) if self.auto_expression else "neutral")).lower()

        if mood in {"happy", "playful"}:
            style = replace(
                base,
                pitch_cents=base.pitch_cents + 45,
                tempo=min(base.tempo + 0.025, 1.18),
                sentence_silence=max(base.sentence_silence - 0.02, 0.08),
            )
        elif mood in {"energetic", "excited"}:
            style = replace(
                base,
                pitch_cents=base.pitch_cents + 25,
                tempo=min(base.tempo + 0.04, 1.20),
            )
        elif mood in {"calm", "sad", "apology"}:
            style = replace(
                base,
                pitch_cents=base.pitch_cents - 80,
                tempo=max(base.tempo - 0.06, 0.88),
                sentence_silence=base.sentence_silence + 0.06,
            )
        elif mood in {"curious", "question"}:
            style = replace(base, pitch_cents=base.pitch_cents + 20)
        else:
            style = base

        if self.pitch_override is not None:
            style = replace(style, pitch_cents=self.pitch_override)
        if self.tempo_override is not None:
            style = replace(style, tempo=self.tempo_override)
        if self.gain_override is not None:
            style = replace(style, gain_db=self.gain_override)
        return style

    async def speak(self, text: str, emotion: str | None = None) -> None:
        style = self.resolve_style(text, emotion)
        logger.info(
            "Voice style: profile={}, emotion={}, pitch={}c, tempo={:.2f}",
            self.profile,
            emotion or self.infer_emotion(text),
            style.pitch_cents,
            style.tempo,
        )
        await self.piper.speak(text, style=style)
