# Nobi 2.7 — Character Update

Powered by RobotOS 2.0.0-beta.8.

# RobotOS 2.0 B2.3 — Streaming Audio Transport

B2.3 replaces the single large `audio_playback` WebSocket frame with an ordered stream:

```text
audio_playback_start
audio_playback_chunk (48 KiB raw audio)
...
audio_playback_end
```

The Raspberry Pi starts `aplay` when the start message arrives and feeds WAV bytes to its stdin as chunks arrive. This prevents WebSocket code 1009 disconnects for long Chatterbox replies, reduces peak memory use, and prepares the playback path for mouth/LED amplitude sync. The legacy `audio_playback` message remains supported for compatibility.

Optional Brain setting:

```text
ROBOTOS_AUDIO_CHUNK_SIZE=49152
```

The default keeps every Base64 WebSocket frame well below 100 KiB. Both Brain and Node retain a 2 MiB safety limit.

# RobotOS 2.0

RobotOS separates the AI Brain, Raspberry Pi Node, and Arduino hardware controller.

## Current milestone: B1.9

The verified conversation path is:

```text
Raspberry Pi microphone
→ WebSocket audio stream
→ Whisper Turbo on Windows
→ transcript filtering
→ short-term conversation memory
→ Ollama robot-greek
→ SPEECH event
→ Piper on Raspberry Pi
→ speakers
```

B1.8 turn-taking remains active: the microphone pauses during Piper playback and resumes after the configurable settling delay.

B1.9 improves conversation quality with:

- up to 10 recent user/assistant turns per connected Node;
- near-duplicate transcript rejection within a short time window;
- a lower Ollama temperature for more stable answers;
- a clearer Greek TTS-oriented system prompt;
- UTF-8 JSONL conversation logging.

## Windows Brain

```powershell
cd C:\RobotOS-2.0
.\.venv\Scripts\Activate.ps1
python -m brain.main
```

Optional configuration:

```powershell
$env:ROBOTOS_OLLAMA_MODEL="robot-greek"
$env:ROBOTOS_OLLAMA_URL="http://127.0.0.1:11434"
$env:ROBOTOS_MAX_HISTORY="10"
$env:ROBOTOS_TRANSCRIPT_DEDUP_SECONDS="3"
$env:ROBOTOS_TRANSCRIPT_SIMILARITY_THRESHOLD="0.92"
$env:ROBOTOS_CONVERSATION_LOG="logs/conversations.jsonl"
```

The Brain sends `think: false` to Ollama. Conversation history is kept in memory only while the Node remains connected. Completed turns are appended to `logs/conversations.jsonl` by default.

## Raspberry Pi Node

The existing permanent environment settings can remain in `~/.bashrc`:

```bash
export ROBOTOS_BRAIN_HOST=192.168.1.26
export ROBOTOS_BRAIN_PORT=8765
export ROBOTOS_MICROPHONE_ENABLED=1
export PIPER_EXECUTABLE="$HOME/RobotOS-2.0/node_runtime/.venv/bin/piper"
export PIPER_MODEL="$HOME/RobotOS-2.0/models/piper/el_GR-rapunzelina-medium.onnx"
export AUDIO_PLAYER=aplay
export ROBOTOS_MIC_RESUME_DELAY=0.4
```

Start the Node:

```bash
cd ~/RobotOS-2.0
source node_runtime/.venv/bin/activate
python -m node.main
```

## B1.9 hardware test

Ask a connected pair of questions:

```text
Πώς σε λένε;
Και ποιος σε έφτιαξε;
```

The second answer should use the previous exchange as context. The Brain log should include `Conversation memory updated`, and the conversation file should contain one JSON object per completed turn.

## Validation

```bash
pytest
python -m compileall brain node shared tests
```

## B2.0 Cartoon Voice Engine

The Node now wraps Piper with an expressive voice engine. The default `cartoon` profile combines Piper prosody controls with optional SoX pitch and tempo processing.

On Raspberry Pi install SoX once:

```bash
sudo apt update
sudo apt install -y sox
```

Add these persistent settings to `~/.bashrc`:

```bash
export ROBOTOS_VOICE_PROFILE=cartoon
export ROBOTOS_VOICE_AUTO_EXPRESSION=1
export ROBOTOS_VOICE_POSTPROCESS=1
```

Profiles:

- `classic`: original voice with minimal processing.
- `cartoon`: brighter and slightly faster; recommended default.
- `energetic`: faster, stronger delivery.
- `kid`: higher and playful.
- `calm`: slower and softer.

Optional manual overrides:

```bash
export ROBOTOS_VOICE_PITCH=180
export ROBOTOS_VOICE_TEMPO=1.06
export ROBOTOS_VOICE_GAIN_DB=0.5
```

Unset an override to return to the selected profile defaults. Logs show the selected profile, inferred expression, pitch, and tempo for every reply.

## B2.1 high-quality local voice

RobotOS can now synthesize speech on the Windows Brain with Chatterbox Multilingual and stream the generated WAV to the Raspberry Pi. This is fully local and has no usage billing or API quota. Piper remains available as an automatic fallback.

Install the optional Brain backend with Python 3.11:

```powershell
pip install -r requirements-chatterbox.txt
```

Select it before starting the Brain:

```powershell
$env:ROBOTOS_TTS_ENGINE="chatterbox"
$env:ROBOTOS_CHATTERBOX_DEVICE="cuda"
$env:ROBOTOS_CHATTERBOX_LANGUAGE="el"
$env:ROBOTOS_CHATTERBOX_REFERENCE_AUDIO="C:\robot\voices\boy_voice_reference.wav"
$env:ROBOTOS_TTS_FALLBACK="1"
python -m brain.main
```

The reference audio is optional. Without it, Chatterbox uses its default voice. The Raspberry Pi requires no extra AI model; it only receives and plays the WAV file.

## B2.2 isolated Chatterbox worker

On Windows, faster-whisper/CTranslate2 and Chatterbox/PyTorch may load incompatible CUDA or cuDNN DLLs when they share one process. B2.2 runs Chatterbox in a persistent subprocess, so both systems can use the RTX GPU without sharing a DLL namespace.

Use the normal Brain settings:

```powershell
$env:ROBOTOS_TTS_ENGINE="chatterbox"
$env:ROBOTOS_CHATTERBOX_DEVICE="cuda"
$env:ROBOTOS_CHATTERBOX_LANGUAGE="el"
$env:ROBOTOS_TTS_FALLBACK="1"
python -m brain.main
```

Expected first-use logs:

```text
Starting isolated Chatterbox worker on cuda
TTS worker: Loading Chatterbox Multilingual on cuda
TTS worker: Chatterbox model loaded
Chatterbox worker ready: pid=...
High-quality TTS generated: engine=chatterbox, bytes=...
```

The first reply loads the model. Later replies reuse the same worker and are faster. The worker automatically prioritizes the cuDNN 9 DLLs bundled with PyTorch and excludes the legacy CUDA v8.9.7 cuDNN path from its own environment.

## B2.4 low-latency settings

The default voice pipeline now ends an utterance after 400 ms of silence, keeps 200 ms of pre-roll, and caps recordings at 8 seconds. Whisper and Chatterbox are preloaded during Brain startup, while Ollama replies are limited for spoken interaction.

Optional overrides:

```text
ROBOTOS_MIC_SILENCE_MS=400
ROBOTOS_MIC_PRE_BUFFER_MS=200
ROBOTOS_MIC_MAX_SECONDS=8
ROBOTOS_MIC_RESUME_DELAY=0.25
ROBOTOS_WHISPER_BEAM_SIZE=1
ROBOTOS_WHISPER_BEST_OF=1
ROBOTOS_WHISPER_VAD_FILTER=0
ROBOTOS_PRELOAD_MODELS=1
ROBOTOS_OLLAMA_NUM_PREDICT=80
ROBOTOS_OLLAMA_NUM_CTX=4096
```

Brain logs now include `stt`, `LLM latency`, `Speech latency`, and total pipeline timing.


## Barge-in (B2.5)

Barge-in is enabled by default. While the robot is speaking, the Node uses a stricter microphone threshold to detect a real user interruption, stops playback, and sends the interrupting utterance to the Brain.

```bash
export ROBOTOS_BARGE_IN_ENABLED=1
export ROBOTOS_BARGE_IN_THRESHOLD=0.06
export ROBOTOS_BARGE_IN_GRACE_MS=650
export ROBOTOS_BARGE_IN_SILENCE_MS=350
export ROBOTOS_BARGE_IN_PRE_BUFFER_MS=180
export ROBOTOS_BARGE_IN_MAX_SECONDS=6
```

Raise `ROBOTOS_BARGE_IN_THRESHOLD` if the robot interrupts itself; lower it if it does not hear a user speaking over playback.

## B2.6 Persona and Emotion Engine

RobotOS now has a canonical character definition in `CHARACTER_BIBLE.md`. The Brain automatically selects one of six speaking styles without making an additional LLM request:

`neutral`, `friendly`, `thinking`, `curious`, `excited`, `funny`.

The style changes Chatterbox expression only; speaking speed remains normal. Disable the engine with `ROBOTOS_EMOTION_ENGINE=0`.


## Nobi 2.6.1 Stability Update

- Rejects recordings shorter than 0.90 seconds before Whisper.
- Rejects low-energy and low-confidence transcripts.
- Blocks known Whisper hallucinations, including `Υπότιτλοι AUTHORWAVE`.
- Invalidates in-flight microphone captures whenever playback starts.
- Uses an 800 ms post-playback cooldown by default.
- Supports both `ROBOTOS_MIC_RESUME_DELAY_MS` and `ROBOTOS_VAD_THRESHOLD`.
- Disables barge-in by default until acoustic echo cancellation is available.
- Introduces the Nobi branding and startup banner.


## Fast Speech Start (Nobi 2.7.1)

Οι απαντήσεις πολλών προτάσεων δεν περιμένουν πλέον να συντεθεί ολόκληρο το WAV. Ο Brain συνθέτει πρώτα την πρώτη φυσική πρόταση και τη στέλνει αμέσως στο Raspberry. Καθώς αυτή αναπαράγεται, το Chatterbox συνθέτει την επόμενη.

Στα logs του Brain εμφανίζονται:

```text
Fast speech first audio ready: 2.10s
TTS segment generated: 1/3
Audio segment dispatched: segment=1/3
```

Στο Raspberry εμφανίζονται:

```text
[AUDIO STREAM] started: speech=..., segment=1/3
[AUDIO STREAM] finished: speech=..., segment=1/3
```

Το μικρόφωνο παραμένει κλειδωμένο μέχρι να ολοκληρωθεί και το τελευταίο segment.

### Low-latency streamed replies (Nobi 2.7.2)

The Brain uses Ollama's streaming chat API. It no longer waits for the complete LLM response before starting TTS. Once a short first sentence is complete, Chatterbox begins synthesis while Ollama continues generating the rest of the reply.

Useful Brain logs:

```text
First-token latency: 0.45s
LLM first sentence ready: 0.82s
TTS segment ready: index=1, tts=2.10s, total_to_audio=2.92s
```
