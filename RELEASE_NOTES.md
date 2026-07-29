# RobotOS 2.0 — B1.7 Release Notes

## Milestone

B1.7 completes the first end-to-end voice conversation path:

**Hear → Understand → Think → Speak**

A Greek utterance captured by the Raspberry Pi is transcribed by Whisper Turbo
on Windows, sent to the local `robot-greek` Ollama model, and spoken by Piper on
the Raspberry Pi.

## Added

- `brain/services/llm.py`
  - Ollama `/api/chat` integration
  - Greek system prompt
  - configurable model, URL, and timeout
  - non-blocking execution with `asyncio.to_thread`
  - clear errors for offline Ollama, HTTP errors, invalid JSON, and empty replies
- Automatic transcript → LLM → speech orchestration in the Brain audio handler.
- Empty-transcript protection.
- Brain configuration variables:
  - `ROBOTOS_OLLAMA_MODEL`
  - `ROBOTOS_OLLAMA_URL`
  - `ROBOTOS_OLLAMA_TIMEOUT_SECONDS`
  - `ROBOTOS_SYSTEM_PROMPT`
- Unit tests for the Ollama service and the complete orchestration path.

## Not included yet

- Conversation history or long-term memory
- Wake word
- Streaming partial speech output
- Internet tools
- Vision
- Arduino motion and mouth synchronization

## Windows validation

```powershell
cd C:\RobotOS-2.0
.\.venv\Scripts\Activate.ps1
pip install -r requirements-brain.txt

ollama list
pytest
python -m compileall brain node shared tests

$env:ROBOTOS_WHISPER_MODEL="turbo"
$env:ROBOTOS_WHISPER_DEVICE="cuda"
$env:ROBOTOS_WHISPER_COMPUTE_TYPE="float16"
$env:ROBOTOS_OLLAMA_MODEL="robot-greek"
python -m brain.main
```

## Raspberry Pi validation

```bash
cd ~/RobotOS-2.0
git pull origin main
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

Say a short phrase such as:

```text
Πώς σε λένε;
```

Success requires all four stages:

1. The Node sends the utterance.
2. The Brain logs the correct transcript.
3. The Brain logs an Ollama response.
4. Piper speaks the response through the Raspberry Pi speakers.
