# RobotOS 2.0

RobotOS 2.0 separates the Windows **Brain**, Raspberry Pi **Node**, and Arduino
hardware layer. Release **B1.6** adds the first end-to-end microphone and Whisper
transcription path while preserving the verified Piper speech pipeline.

## B1.6 audio flow

```text
Raspberry Pi USB microphone
        ↓
AudioRecorder + RMS VAD
        ↓
AUDIO_START / AUDIO_CHUNK / AUDIO_END
        ↓
WebSocket
        ↓
Brain AudioBufferService
        ↓
Whisper Turbo (faster-whisper)
        ↓
TRANSCRIPT
        ↓
Node log
```

Audio is transported as ordered base64-encoded PCM chunks inside validated
RobotOS protocol messages. B1.6 accepts mono, signed 16-bit PCM at 16 kHz.

## Core development setup

```powershell
cd C:\RobotOS-2.0
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pytest
python -m compileall brain node shared tests
```

## Windows Brain setup

Install Brain-only dependencies inside the Windows virtual environment:

```powershell
pip install -r requirements-brain.txt
```

Recommended settings for an RTX 3060:

```powershell
$env:ROBOTOS_WHISPER_MODEL="turbo"
$env:ROBOTOS_WHISPER_DEVICE="cuda"
$env:ROBOTOS_WHISPER_COMPUTE_TYPE="float16"
python -m brain.main
```

The Whisper model is loaded lazily when the first utterance arrives.

## Raspberry Pi Node setup

Install Node-only dependencies inside the Pi virtual environment:

```bash
cd ~/RobotOS-2.0
source node_runtime/.venv/bin/activate
pip install -r requirements-node.txt
```

Configure the Brain and Piper paths:

```bash
export ROBOTOS_BRAIN_HOST=192.168.1.26
export ROBOTOS_BRAIN_PORT=8765
export PIPER_EXECUTABLE=/home/pi/RobotOS-2.0/node_runtime/.venv/bin/piper
export PIPER_MODEL=/home/pi/RobotOS-2.0/models/piper/el_GR-rapunzelina-medium.onnx
export AUDIO_PLAYER=aplay
```

Enable microphone capture explicitly:

```bash
export ROBOTOS_MICROPHONE_ENABLED=1
python -m node.main
```

The microphone listener waits for speech, keeps a short pre-buffer, stops after
silence, and sends the completed utterance to the Brain. The transcript appears
in the Node log as:

```text
[TRANSCRIPT] Καλημέρα RobotOS
```

## Microphone tuning

The defaults are conservative and can be overridden:

```bash
export ROBOTOS_MIC_THRESHOLD=0.015
export ROBOTOS_MIC_SILENCE_MS=700
export ROBOTOS_MIC_PRE_BUFFER_MS=300
export ROBOTOS_MIC_MAX_SECONDS=15
```

Raise `ROBOTOS_MIC_THRESHOLD` if ambient noise triggers recording. Lower it if
quiet speech is not detected.

## Existing Piper test

With Brain and Node running, speech can still be tested from Windows:

```powershell
python -m brain.send_speech
```

See `RELEASE_NOTES.md` for the complete B1.6 validation sequence.
