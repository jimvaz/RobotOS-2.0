# Changelog

## B1.7

### Added
- Ollama/Qwen language-model service on the Windows Brain.
- Full transcript → LLM response → SPEECH event pipeline.
- Greek voice-oriented system prompt.
- Configurable Ollama model, endpoint, timeout, and system prompt.
- Explicit `llm_failed` protocol error handling.
- Tests for successful Ollama requests, offline Ollama, empty prompts, and the
  complete audio-to-speech orchestration path.

### Changed
- RobotOS version advanced to `2.0.0-alpha.3`.
- B1.6 audio handler now ignores empty transcripts and optionally invokes the
  LLM/speech services.
- Documentation updated for the first complete voice conversation loop.

## B1.6

### Added
- Raspberry Pi microphone recorder with RMS voice activity detection.
- PCM audio streaming through `AUDIO_START`, `AUDIO_CHUNK`, and `AUDIO_END`.
- Brain-side ordered audio buffering and Whisper Turbo transcription.
- `TRANSCRIPT` responses and audio-pipeline tests.

## B1.5.2

### Added
- Background speech queue and Piper playback integration on the Node.
- Sequential, non-blocking speech delivery and graceful shutdown.
