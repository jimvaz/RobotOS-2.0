# RobotOS 2.0

RobotOS 2.0 separates the Windows **Brain**, Raspberry Pi **Node**, and Arduino
hardware layer. Release **B1.7** completes the first full Greek voice loop:

```text
Raspberry Pi microphone
        ↓
Whisper Turbo on Windows
        ↓
Greek transcript
        ↓
Ollama / Qwen (robot-greek)
        ↓
SPEECH event
        ↓
Piper on Raspberry Pi
        ↓
Robot voice
```

The B1.6 microphone, WebSocket, transcription, speech queue, and Piper paths are
preserved. B1.7 adds a lazy, non-blocking Ollama service and connects every
non-empty transcript to a generated spoken response.

## Core development setup

```powershell
cd C:\RobotOS-2.0
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-brain.txt
pytest
python -m compileall brain node shared tests
```

## Windows Brain setup

Ollama must be running and the configured model must exist:

```powershell
ollama list
ollama run robot-greek
```

Exit the interactive Ollama prompt after confirming the model works, then start
the Brain:

```powershell
cd C:\RobotOS-2.0
.\.venv\Scripts\Activate.ps1

$env:ROBOTOS_WHISPER_MODEL="turbo"
$env:ROBOTOS_WHISPER_DEVICE="cuda"
$env:ROBOTOS_WHISPER_COMPUTE_TYPE="float16"
$env:ROBOTOS_OLLAMA_MODEL="robot-greek"
$env:ROBOTOS_OLLAMA_URL="http://127.0.0.1:11434"

python -m brain.main
```

Optional settings:

```powershell
$env:ROBOTOS_OLLAMA_TIMEOUT_SECONDS="120"
$env:ROBOTOS_SYSTEM_PROMPT="Απαντάς μόνο στα ελληνικά, σύντομα και ευγενικά."
```

The Brain uses Ollama's local `/api/chat` endpoint. The HTTP request runs in a
worker thread so Whisper/Ollama processing does not block WebSocket heartbeats.

## Raspberry Pi Node setup

```bash
cd ~/RobotOS-2.0
source node_runtime/.venv/bin/activate
pip install -r requirements-node.txt

export ROBOTOS_BRAIN_HOST=192.168.1.26
export ROBOTOS_BRAIN_PORT=8765
export ROBOTOS_MICROPHONE_ENABLED=1

export PIPER_EXECUTABLE="$HOME/RobotOS-2.0/node_runtime/.venv/bin/piper"
export PIPER_MODEL="$HOME/RobotOS-2.0/models/piper/el_GR-rapunzelina-medium.onnx"
export AUDIO_PLAYER=aplay

python -m node.main
```

After the handshake, speak near the Raspberry Pi microphone. Expected Brain
logs include:

```text
Transcript: 'Πώς σε λένε;'
LLM response generated: model=robot-greek, text='Είμαι το RobotOS.'
Speech dispatched: recipients=1
```

The Node should then queue and play the answer through Piper.

## Microphone tuning

```bash
export ROBOTOS_MIC_THRESHOLD=0.015
export ROBOTOS_MIC_SILENCE_MS=700
export ROBOTOS_MIC_PRE_BUFFER_MS=300
export ROBOTOS_MIC_MAX_SECONDS=15
```

Raise the threshold if ambient noise triggers recording. Lower it if quiet
speech is not detected.

## Failure behaviour

- Empty Whisper transcripts are ignored and are not sent to Ollama.
- If Ollama is offline, the Brain sends an `llm_failed` protocol error and keeps
  the WebSocket connection alive.
- If Whisper fails, the existing `whisper_failed` error path remains active.
- Conversation history is intentionally not included in B1.7; every utterance is
  currently an independent request.

See `RELEASE_NOTES.md` for the validation checklist.
