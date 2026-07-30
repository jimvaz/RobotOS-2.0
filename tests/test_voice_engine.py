"""Tests for the B2.0 expressive voice engine."""

from __future__ import annotations

import asyncio
from typing import Any

from node.tts.voice_engine import VoiceEngine


class FakePiper:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    async def speak(self, text: str, *, style: Any = None) -> None:
        self.calls.append((text, style))


def test_cartoon_profile_is_default_and_raises_pitch() -> None:
    engine = VoiceEngine(FakePiper())
    style = engine.resolve_style("Αυτή είναι μια απάντηση.")

    assert style.name == "cartoon"
    assert style.pitch_cents > 0
    assert style.tempo > 1.0


def test_voice_engine_infers_happy_greeting() -> None:
    engine = VoiceEngine(FakePiper())
    neutral = engine.resolve_style("Αυτή είναι μια πληροφορία.", "neutral")
    happy = engine.resolve_style("Γεια σου!", None)

    assert engine.infer_emotion("Γεια σου!") == "happy"
    assert happy.pitch_cents > neutral.pitch_cents
    assert happy.tempo > neutral.tempo


def test_voice_engine_uses_calm_style_for_apology() -> None:
    engine = VoiceEngine(FakePiper())
    neutral = engine.resolve_style("Εντάξει.", "neutral")
    calm = engine.resolve_style("Συγγνώμη, δεν το κατάλαβα.")

    assert engine.infer_emotion("Συγγνώμη, δεν το κατάλαβα.") == "calm"
    assert calm.pitch_cents < neutral.pitch_cents
    assert calm.tempo < neutral.tempo


def test_voice_overrides_take_precedence() -> None:
    engine = VoiceEngine(
        FakePiper(),
        pitch_override=250,
        tempo_override=1.12,
        gain_override=1.5,
    )
    style = engine.resolve_style("Γεια σου!")

    assert style.pitch_cents == 250
    assert style.tempo == 1.12
    assert style.gain_db == 1.5


def test_voice_engine_passes_explicit_emotion_to_piper() -> None:
    async def scenario() -> tuple[str, Any]:
        piper = FakePiper()
        engine = VoiceEngine(piper)
        await engine.speak("Δοκιμή", "calm")
        return piper.calls[0]

    text, style = asyncio.run(scenario())
    assert text == "Δοκιμή"
    assert style.tempo <= 1.0
