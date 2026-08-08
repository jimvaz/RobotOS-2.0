## Nobi 2.7.3.1 — PC Mic Bugfixes

- Cancels an in-flight PC microphone capture as soon as Nobi playback starts, including a second gate check immediately after a blocking PortAudio read.
- Preserves Ollama streaming chunks exactly so token boundaries no longer introduce spaces inside Greek words.
- Uses the verified HIK microphone MME device `1` as the default PC microphone input; it remains overridable with `ROBOTOS_BRAIN_MIC_DEVICE`.


## Nobi 2.7.1 — Fast Speech Start

- Χωρίζει τις απαντήσεις σε σύντομα φυσικά τμήματα ανά πρόταση.
- Συνθέτει και αποστέλλει την πρώτη πρόταση αμέσως, χωρίς να περιμένει ολόκληρη την απάντηση.
- Παράγει την επόμενη πρόταση ενώ το Raspberry αναπαράγει την προηγούμενη.
- Κρατά το μικρόφωνο κλειδωμένο σε ολόκληρη την ακολουθία προτάσεων.
- Προσθέτει ενιαίο `speech_id`, αρίθμηση segments και ασφαλή ακύρωση ακολουθίας.
- Προσθέτει latency logs για τον χρόνο μέχρι το πρώτο έτοιμο audio segment.
- Διατηρεί την ίδια φωνή, ταχύτητα, Persona και Emotion Engine.


## B2.5 — Interruptible Speech / Barge-In

- Added `speech_interrupt` protocol event.
- Node monitors for a louder, sustained user utterance while robot audio is playing.
- Active streamed or legacy playback is stopped immediately on barge-in.
- The captured interrupting utterance is sent directly to the Brain.
- Added configurable grace, threshold, silence, pre-buffer, and maximum capture values.
- Brain can cancel an outgoing stream when a Node takes the turn.
- Version `2.0.0-beta.6`.
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

## RobotOS-2.0 B2.6 — Persona & Emotion Engine

This release gives RobotOS a stable Greek-speaking character and dynamically changes the expression of the same Chatterbox voice according to the response. The engine is deterministic and adds no extra LLM request, preserving latency.

Enable or disable it with:

```text
ROBOTOS_EMOTION_ENGINE=1
```

The official character definition is stored in `CHARACTER_BIBLE.md`.


## Nobi 2.6.1 Stability Update

- Rejects recordings shorter than 0.90 seconds before Whisper.
- Rejects low-energy and low-confidence transcripts.
- Blocks known Whisper hallucinations, including `Υπότιτλοι AUTHORWAVE`.
- Invalidates in-flight microphone captures whenever playback starts.
- Uses an 800 ms post-playback cooldown by default.
- Supports both `ROBOTOS_MIC_RESUME_DELAY_MS` and `ROBOTOS_VAD_THRESHOLD`.
- Disables barge-in by default until acoustic echo cancellation is available.
- Introduces the Nobi branding and startup banner.

## Nobi 2.7 — Character Update

Η έκδοση 2.7 επικεντρώνεται αποκλειστικά στον χαρακτήρα και στη φυσικότητα της συνομιλίας. Ο Nobi δεν έχει πλέον μότο. Διαθέτει γρήγορες, εναλλασσόμενες κοινωνικές απαντήσεις και αποφεύγει εκφράσεις που θυμίζουν chatbot ή γλωσσικό μοντέλο. Το audio, Whisper, WebSocket και Chatterbox pipeline παραμένουν αμετάβλητα.

## Nobi 2.7.2 — First Response Latency

This release reduces the delay before Nobi's first spoken words. Ollama now streams its response, and the Brain starts Chatterbox synthesis as soon as the first complete sentence becomes available. The remainder of the answer continues generating while the first segment is synthesized and played.

New diagnostic logs include `First-token latency`, `LLM first sentence ready`, and `total_to_audio`, making the remaining bottleneck measurable on the target PC.

## Nobi 2.7.3 — PC Microphone Mode

The Windows Brain can now listen directly through a local microphone while the Raspberry Pi remains responsible for speaker playback and future robot hardware. The tested default is the HIK 4K USB camera microphone on MME device 1 at 48 kHz. Audio is converted to 16 kHz mono PCM before Whisper.

Recommended Windows settings:

```powershell
$env:ROBOTOS_BRAIN_MICROPHONE_ENABLED="1"
$env:ROBOTOS_BRAIN_MIC_DEVICE="1"
$env:ROBOTOS_BRAIN_MIC_SAMPLE_RATE="48000"
$env:ROBOTOS_BRAIN_MIC_TARGET_RATE="16000"
$env:ROBOTOS_BRAIN_MIC_THRESHOLD="0.010"
$env:ROBOTOS_BRAIN_MIC_SILENCE_MS="450"
$env:ROBOTOS_BRAIN_MIC_PRE_BUFFER_MS="300"
$env:ROBOTOS_BRAIN_MIC_COOLDOWN_MS="500"
```

Disable Raspberry microphone capture:

```bash
export ROBOTOS_MICROPHONE_ENABLED=0
```

## Nobi 2.7.3.2 — Hard Playback Lock

- Replaced estimated WAV-duration microphone gating with an authoritative playback ACK.
- Brain hard-locks the PC microphone for the entire speech sequence, including TTS gaps between segments.
- Raspberry Node sends `audio_playback_finished` only after `aplay` finishes the final segment.
- Brain releases the PC microphone only after that ACK plus the configured cooldown.
- Added regression coverage for the hard lock and playback-finished protocol payload.


## Nobi 2.7.3.3 — Adaptive Listening

- PC microphone endpointing now adapts to how long the user has been speaking.
- Short requests use 650 ms of silence for a fast response.
- After 3 seconds of speech, the pause allowance grows to 850 ms.
- After 7 seconds, it grows to 1200 ms so longer questions can include natural thinking pauses.
- Maximum utterance length is now 30 seconds by default.
- Hard Playback Lock remains unchanged, so adaptive listening never records Nobi's own playback.
- Existing `ROBOTOS_BRAIN_MIC_SILENCE_MS` values are respected as a minimum and are never shortened.

Optional tuning:

```text
ROBOTOS_BRAIN_MIC_ADAPTIVE=1
ROBOTOS_BRAIN_MIC_SILENCE_MS=650
ROBOTOS_BRAIN_MIC_MEDIUM_AFTER_SECONDS=3.0
ROBOTOS_BRAIN_MIC_MEDIUM_SILENCE_MS=850
ROBOTOS_BRAIN_MIC_LONG_AFTER_SECONDS=7.0
ROBOTOS_BRAIN_MIC_LONG_SILENCE_MS=1200
ROBOTOS_BRAIN_MIC_MAX_SECONDS=30
```
