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
