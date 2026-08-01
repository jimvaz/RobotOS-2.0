from __future__ import annotations
import asyncio
import os
from pathlib import Path

from brain.services.tts import ChatterboxWorkerTTS, build_worker_environment
from brain.services.tts_worker import extract_text


def test_worker_environment_prioritizes_torch_and_removes_legacy_cudnn() -> None:
    env = build_worker_environment(
        {
            "PATH": os.pathsep.join(
                [
                    r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v8.9.7\bin",
                    r"C:\Windows\System32",
                ]
            ),
            "SystemRoot": r"C:\Windows",
        }
    )
    entries = env["PATH"].split(os.pathsep)
    assert "torch" in entries[0].lower()
    assert all("v8.9.7" not in entry.lower() for entry in entries)


def test_chatterbox_worker_is_persistent_and_returns_audio() -> None:
    async def scenario() -> tuple[bytes, bytes, int | None]:
        backend = ChatterboxWorkerTTS(
            device="cpu",
            worker_module="tests.fake_tts_worker",
            startup_timeout=10,
            synthesis_timeout=10,
        )
        first = await backend.synthesize("Γεια")
        pid = backend._process.pid if backend._process else None
        second = await backend.synthesize("Ξανά")
        assert backend._process is not None
        assert backend._process.pid == pid
        await backend.close()
        return first, second, pid

    first, second, pid = asyncio.run(scenario())
    assert first == b"RIFF-worker-wave"
    assert second == b"RIFF-worker-wave"
    assert pid is not None


def test_worker_environment_forces_utf8_protocol() -> None:
    env = build_worker_environment({"PATH": "", "SystemRoot": r"C:\Windows"})
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_extract_text_preserves_greek_as_plain_string() -> None:
    text = extract_text({"text": "  Καλημέρα, με ακούς;  "})
    assert type(text) is str
    assert text == "Καλημέρα, με ακούς;"


def test_extract_text_rejects_non_string_value() -> None:
    import pytest
    with pytest.raises(TypeError, match="must be str"):
        extract_text({"text": {"value": "Γεια"}})


def test_chatterbox_preload_starts_worker_without_synthesis() -> None:
    async def scenario() -> int | None:
        backend = ChatterboxWorkerTTS(
            device="cpu",
            worker_module="tests.fake_tts_worker",
            startup_timeout=10,
            synthesis_timeout=10,
        )
        await backend.preload()
        pid = backend._process.pid if backend._process else None
        await backend.close()
        return pid

    assert asyncio.run(scenario()) is not None
