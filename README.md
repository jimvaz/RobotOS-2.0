# RobotOS 2.0

RobotOS separates the AI Brain, Raspberry Pi Node, and Arduino hardware controller.

## Current milestone: B1.8

The verified conversation path is:

```text
Raspberry Pi microphone
→ WebSocket audio stream
→ Whisper Turbo on Windows
→ Ollama robot-greek
→ SPEECH event
→ Piper on Raspberry Pi
→ speakers
```

B1.8 adds turn-taking so the microphone does not hear the robot's own voice:

```text
LISTENING
→ user utterance
→ PROCESSING
→ MIC paused
→ Piper playback
→ 400 ms settling delay
→ MIC resumed
→ LISTENING
```

If playback begins while the microphone is already recording, that partial recording is discarded rather than sent to Whisper.

## Windows Brain

```powershell
cd C:\RobotOS-2.0
.\.venv\Scripts\Activate.ps1
python -m brain.main
```

Relevant Ollama configuration:

```powershell
$env:ROBOTOS_OLLAMA_MODEL="robot-greek"
$env:ROBOTOS_OLLAMA_URL="http://127.0.0.1:11434"
```

The Brain sends `think: false` to Ollama so the final Greek response is returned directly.

## Raspberry Pi Node

```bash
cd ~/RobotOS-2.0
source .venv/bin/activate
export ROBOTOS_BRAIN_HOST=<WINDOWS_IP>
export ROBOTOS_MICROPHONE_ENABLED=1
export ROBOTOS_MIC_RESUME_DELAY=0.4
python -m node.main
```

Expected turn-taking logs:

```text
MIC paused
[SPEECH] started: '...'
[SPEECH] finished: '...'
MIC resumed
```

Increase `ROBOTOS_MIC_RESUME_DELAY` to `0.6` or `0.8` only when the room or speakers have a noticeable echo tail.

## Validation

```bash
pytest
python -m compileall brain node shared tests
```
