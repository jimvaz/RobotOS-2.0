# RobotOS 2.0

RobotOS 2.0 separates the Windows **Brain**, Raspberry Pi **Node**, and Arduino
hardware layer. Release B1.5.2 provides an audible Brain-to-Node speech path.

## Requirements

- Python 3.11+
- Brain: Windows or Linux with network access to the Node
- Node: Raspberry Pi with Piper, a Greek voice model, ALSA, and speakers

## Development setup

```powershell
cd C:\RobotOS-2.0
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pytest
```

## B1.5.2 speech flow

```text
Brain SpeechService
        ↓
WebSocket SPEECH event
        ↓
NodeMessageRouter
        ↓
Node speech handler
        ↓
SpeechQueue
        ↓
PiperTTS
        ↓
Raspberry Pi speakers
```

## Node Piper configuration

```bash
export PIPER_EXECUTABLE=piper
export PIPER_MODEL=/home/pi/robot/models/el_GR-rapunzelina-medium.onnx
export AUDIO_PLAYER=aplay
```

Start the Brain and Node with their existing entry points, then run:

```powershell
python -m brain.send_speech
```

Messages are queued and played sequentially. Piper failures are logged and do
not terminate the Node or prevent later messages from being spoken.

See `RELEASE_NOTES.md` for the complete B1.5.2 validation procedure.
