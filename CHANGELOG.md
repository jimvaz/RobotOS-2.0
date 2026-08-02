
## B2.5 — Interruptible Speech / Barge-In

- Added `speech_interrupt` protocol event.
- Node monitors for a louder, sustained user utterance while robot audio is playing.
- Active streamed or legacy playback is stopped immediately on barge-in.
- The captured interrupting utterance is sent directly to the Brain.
- Added configurable grace, threshold, silence, pre-buffer, and maximum capture values.
- Brain can cancel an outgoing stream when a Node takes the turn.
- Version `2.0.0-beta.6`.
# Changelog

## 2.0.0-beta.5 — B2.4 Low-Latency Voice Pipeline

- Reduced microphone endpoint silence from 700 ms to 400 ms by default.
- Reduced pre-buffer from 300 ms to 200 ms and maximum utterance from 15 s to 8 s.
- Reduced post-playback microphone delay to 250 ms.
- Added configurable fast Whisper decoding (`beam_size=1`, `best_of=1`) and disabled redundant Whisper VAD by default because endpointing already happens on the Node.
- Added startup preloading for Whisper and the persistent Chatterbox worker.
- Limited Ollama replies with configurable `num_predict=80` and `num_ctx=4096`.
- Added per-stage latency logs for STT, LLM, TTS, and the complete pipeline.
- Version bumped to `2.0.0-beta.5`.

## 2.0.0-beta.4 — B2.3

- Added streamed Brain audio protocol: `audio_playback_start`, `audio_playback_chunk`, and `audio_playback_end`.
- Replaced one large Base64 WAV frame with configurable 48 KiB chunks.
- Added Raspberry Pi stdin playback so audio begins while chunks are still arriving.
- Added strict stream IDs, sequence ordering, byte counts, and chunk-count validation.
- Added stream cleanup on disconnect, replacement, errors, and Node shutdown.
- Retained legacy `audio_playback` compatibility and Piper fallback.
- Added regression coverage for 10 MiB generated audio without oversized WebSocket frames.
- Removed generated test WAV files from the release archive.

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

## 2.0.0-beta.7 — B2.6 Persona & Emotion Engine

- Added the canonical RobotOS Character Bible and persona prompt.
- Added deterministic low-latency emotion classification.
- Added neutral, friendly, thinking, curious, excited, and funny voice styles.
- Chatterbox now receives dynamic `exaggeration` and `cfg_weight` per response.
- Preserved normal speaking speed and the existing low-latency pipeline.
