# Changelog

## 2.0.0-alpha.5 — B1.9

- Added bounded per-node short-term conversation memory.
- Added conversation history to Ollama `/api/chat` requests.
- Added configurable near-duplicate transcript filtering.
- Added UTF-8 JSONL conversation logging.
- Reduced LLM temperature to 0.2 and improved the Greek system prompt.
- Added B1.9 unit and integration tests.

## 2.0.0-alpha.4 — B1.8

### Added

- Microphone pause/resume lifecycle around Piper playback.
- `AudioRecorder.pause()`, `resume()`, `paused`, and `wait_until_resumed()`.
- Immediate cancellation and disposal of an in-progress microphone utterance when speech playback begins.
- Configurable `ROBOTOS_MIC_RESUME_DELAY` with a default of 0.4 seconds.
- SpeechQueue lifecycle hooks and `speaking` state.
- Tests for turn-taking and failure-safe microphone recovery.

### Changed

- Node microphone loop now waits until playback has fully completed before recording again.
- Speech logs now clearly identify playback start and finish.
- Ollama chat requests disable thinking mode.

## 2.0.0-alpha.3 — B1.7

- Added the Whisper → Ollama → Piper conversational pipeline.

## B2.0 - Cartoon Voice Engine

- Added configurable expressive voice profiles: `classic`, `cartoon`, `energetic`, `kid`, and `calm`.
- Added lightweight automatic expression detection for greetings, questions, jokes, apologies, and excited replies.
- Added Piper prosody controls for length, noise, and sentence silence.
- Added optional SoX post-processing for pitch, tempo, and gain.
- Preserved raw Piper playback as an automatic fallback when SoX is unavailable or fails.
- Added environment overrides for voice tuning and tests for profile selection.
- Updated RobotOS version to `2.0.0-beta.1`.

## B2.1 — Local High-Quality TTS

- Added optional Chatterbox Multilingual synthesis on the Windows Brain.
- Added `AUDIO_PLAYBACK` protocol messages for WAV delivery to Raspberry Pi.
- Added a Node audio playback queue with microphone pause/resume lifecycle.
- Kept Piper as the automatic fallback when Chatterbox is unavailable or fails.
- Added configurable TTS engine, CUDA device, language and reference voice path.
- Added tests for audio transport and backend selection.
- Version updated to `2.0.0-beta.2`.

## 2.0.0-beta.3 — B2.2

- Moved Chatterbox synthesis into a persistent isolated Python subprocess.
- Prevented Windows CUDA/cuDNN DLL conflicts between faster-whisper/CTranslate2 and PyTorch.
- Added JSON-line worker protocol with temporary WAV handoff.
- Chatterbox now loads once and remains resident for subsequent replies.
- Added worker startup/synthesis timeouts and graceful shutdown.
- Added automatic worker PATH sanitization that prioritizes PyTorch cuDNN 9 and removes legacy cuDNN 8.9.7 paths.
- Retained automatic Raspberry Pi Piper fallback when the worker fails.
- Added tests for worker persistence and DLL environment isolation.

## 2.0.0-beta.3.1 — B2.2.1

- Fixed the isolated TTS worker protocol to read and write explicit UTF-8 bytes on Windows.
- Prevented Greek synthesis text from being decoded through the active Windows console code page.
- Added strict string validation and NFC normalization before Chatterbox tokenization.
- Forced UTF-8 mode in the worker environment and added regression tests.
