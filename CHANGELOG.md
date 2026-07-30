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
