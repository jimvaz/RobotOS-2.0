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


def test_playback_gate_hard_lock() -> None:
    gate = PlaybackGate(cooldown_seconds=0.1)
    gate.begin("speech-1")
    assert gate.blocked


@pytest.mark.asyncio
async def test_playback_gate_opens_only_after_ack_and_cooldown() -> None:
    gate = PlaybackGate(cooldown_seconds=0.01)
    gate.begin("speech-1")
    await gate.finish("speech-1")
    await asyncio.wait_for(gate.wait_until_open(), timeout=0.2)
    assert not gate.blocked

def test_local_microphone_config_defaults() -> None:
    cfg = LocalMicrophoneConfig(device=1)
    assert cfg.capture_rate == 48000
    assert cfg.target_rate == 16000
    assert cfg.device == 1


def _listener_for_endpoint(cfg: LocalMicrophoneConfig) -> LocalMicrophoneListener:
    async def submit(_pcm: bytes, _rate: int, _language: str) -> None:
        return None
    return LocalMicrophoneListener(cfg, submit, PlaybackGate(cooldown_seconds=0.0))


def test_adaptive_endpoint_windows() -> None:
    listener = _listener_for_endpoint(LocalMicrophoneConfig(device=1))
    assert listener._endpoint_silence_ms(1.5) == 650
    assert listener._endpoint_silence_ms(3.0) == 850
    assert listener._endpoint_silence_ms(6.9) == 850
    assert listener._endpoint_silence_ms(7.0) == 1200


def test_explicit_silence_setting_is_never_shortened() -> None:
    listener = _listener_for_endpoint(LocalMicrophoneConfig(device=1, silence_ms=900))
    assert listener._endpoint_silence_ms(1.0) == 900
    assert listener._endpoint_silence_ms(4.0) == 900
    assert listener._endpoint_silence_ms(8.0) == 1200


def test_adaptive_endpoint_can_be_disabled() -> None:
    listener = _listener_for_endpoint(
        LocalMicrophoneConfig(device=1, silence_ms=850, adaptive_listening=False)
    )
    assert listener._endpoint_silence_ms(20.0) == 850
