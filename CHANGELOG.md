# Changelog

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
