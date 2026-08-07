from __future__ import annotations

import asyncio
import wave
from io import BytesIO

import numpy as np
import pytest

from brain.audio.local_microphone import LocalMicrophoneConfig, LocalMicrophoneListener
from brain.audio.playback_gate import PlaybackGate


def _wav_bytes(seconds: float = 0.1, sample_rate: int = 16000) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * int(seconds * sample_rate))
    return buffer.getvalue()


def test_resample_48k_to_16k_pcm() -> None:
    source = np.zeros(48000, dtype=np.float32)
    pcm = LocalMicrophoneListener._resample_to_int16(source, 48000, 16000)
    assert len(pcm) == 16000 * 2


def test_playback_gate_reserves_wav_duration() -> None:
    gate = PlaybackGate(cooldown_seconds=0.1)
    duration = gate.reserve_wav(_wav_bytes(0.2))
    assert duration == pytest.approx(0.2, abs=0.01)
    assert gate.blocked


@pytest.mark.asyncio
async def test_playback_gate_eventually_opens() -> None:
    gate = PlaybackGate(cooldown_seconds=0.0)
    gate.reserve_seconds(0.01)
    await asyncio.wait_for(gate.wait_until_open(), timeout=0.2)
    assert not gate.blocked


def test_local_microphone_config_defaults() -> None:
    cfg = LocalMicrophoneConfig(device=1)
    assert cfg.capture_rate == 48000
    assert cfg.target_rate == 16000
    assert cfg.device == 1
