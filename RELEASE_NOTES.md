# RobotOS 2.0.0-beta.5 — B2.4

This release focuses on response speed. The Raspberry Pi stops recording sooner after the user finishes speaking, Whisper uses fast decoding, the Brain preloads Whisper and Chatterbox at startup, and Ollama produces shorter speech-friendly answers. Detailed stage timings make remaining bottlenecks measurable.

Expected improvement depends on hardware and phrase length. This release reduces avoidable waiting but does not yet implement token-by-token LLM or true incremental Chatterbox synthesis.

# RobotOS 2.0 B2.3 — Streaming Audio Engine

B2.3 fixes long Chatterbox responses disconnecting the Raspberry Pi with WebSocket code 1009. Generated WAV data is now transported as small ordered chunks and played through `aplay` stdin on the Node.

Expected Node logs:

```text
[AUDIO STREAM] started: id=..., engine=chatterbox, bytes=...
[AUDIO STREAM] finished: id=..., chunks=..., bytes=...
```

The microphone remains paused for the complete playback lifecycle and resumes after the configured acoustic settling delay.

# RobotOS 2.0 B2.2 — Isolated Chatterbox Worker

B2.2 fixes the Windows CUDA/cuDNN collision observed when faster-whisper and Chatterbox ran inside the same Python process.

## Architecture

The Brain continues to run Whisper, Ollama integration, WebSocket routing and conversation memory. Chatterbox now runs in a separate persistent Python worker process:

```text
Raspberry Pi microphone
        ↓
Brain process: Whisper → Ollama
        ↓ JSON-line IPC
Chatterbox worker process: PyTorch CUDA → WAV
        ↓
Brain → WebSocket audio playback → Raspberry Pi speakers
```

The worker loads Chatterbox once, remains resident between replies and uses the PyTorch-bundled cuDNN 9 DLLs. This isolates it from CUDA/cuDNN libraries loaded by CTranslate2 in the Brain process.

## New settings

```text
ROBOTOS_CHATTERBOX_STARTUP_TIMEOUT=180
ROBOTOS_CHATTERBOX_SYNTHESIS_TIMEOUT=180
```

All B2.1 settings remain supported. Piper remains the automatic Node fallback.
