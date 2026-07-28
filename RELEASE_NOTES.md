# RobotOS 2.0 — B1.6

## Summary

B1.6 gives RobotOS its first working hearing pipeline. The Raspberry Pi captures
one spoken utterance, streams validated PCM chunks to the Windows Brain, and the
Brain transcribes the audio with faster-whisper before returning a `TRANSCRIPT`
message to the originating Node.

The previously verified B1.5.2 Brain-to-Node Piper path remains intact.

## Added

- Protocol message types:
  - `AUDIO_START`
  - `AUDIO_CHUNK`
  - `AUDIO_END`
  - `TRANSCRIPT`
- Shared validated payload models with base64 encoding and decoding.
- Ordered, bounded `AudioBufferService` sessions scoped per connection.
- Lazy-loading `WhisperService` using faster-whisper.
- Brain audio handlers with structured protocol errors.
- Raspberry Pi `AudioRecorder` using 16 kHz mono int16 PCM.
- Simple RMS voice activity detection with silence timeout and pre-buffer.
- `AudioStreamer` with ordered chunk sequencing.
- Node transcript handler and transcript logging.
- Opt-in continuous microphone task in `NodeClient`.
- Separate `requirements-brain.txt` and `requirements-node.txt` files.
- Six audio-pipeline tests.

## Safety and resilience

- Microphone capture is disabled by default and must be enabled with
  `ROBOTOS_MICROPHONE_ENABLED=1`.
- Audio sessions reject duplicate starts, unknown sessions, out-of-order chunks,
  incorrect final chunk counts, invalid base64, and oversized audio buffers.
- A disconnected Node has all unfinished audio sessions discarded.
- Whisper and microphone dependencies are imported lazily so the core test suite
  does not require audio hardware, CUDA, or a downloaded model.

## Windows Brain configuration

```powershell
cd C:\RobotOS-2.0
.\.venv\Scripts\Activate.ps1
pip install -r requirements-brain.txt

$env:ROBOTOS_WHISPER_MODEL="turbo"
$env:ROBOTOS_WHISPER_DEVICE="cuda"
$env:ROBOTOS_WHISPER_COMPUTE_TYPE="float16"
python -m brain.main
```

Expected startup:

```text
Starting WebSocket server on ws://0.0.0.0:8765
Waiting for RobotOS nodes...
```

## Raspberry Pi configuration

```bash
cd ~/RobotOS-2.0
source node_runtime/.venv/bin/activate
pip install -r requirements-node.txt

export ROBOTOS_BRAIN_HOST=192.168.1.26
export ROBOTOS_BRAIN_PORT=8765
export PIPER_EXECUTABLE=/home/pi/RobotOS-2.0/node_runtime/.venv/bin/piper
export PIPER_MODEL=/home/pi/RobotOS-2.0/models/piper/el_GR-rapunzelina-medium.onnx
export AUDIO_PLAYER=aplay
export ROBOTOS_MICROPHONE_ENABLED=1

python -m node.main
```

Speak one short Greek phrase after the handshake. Expected Pi logs include:

```text
Microphone listener enabled
Audio utterance sent: session=..., bytes=...
[TRANSCRIPT] Καλημέρα RobotOS
```

Expected Brain logs include:

```text
Audio session started: ...
Audio session completed: session=..., bytes=...
Transcript: 'Καλημέρα RobotOS'
```

## Tuning

```bash
export ROBOTOS_MIC_THRESHOLD=0.015
export ROBOTOS_MIC_SILENCE_MS=700
export ROBOTOS_MIC_PRE_BUFFER_MS=300
export ROBOTOS_MIC_MAX_SECONDS=15
```

## Validation completed for the release archive

```text
pytest: 34 passed
compileall: passed
```

Commands to repeat locally:

```powershell
pytest
python -m compileall brain node shared tests
```

## Scope intentionally deferred

B1.6 does not yet connect transcripts to Qwen, conversation memory, wake-word
detection, or echo cancellation. These belong to later milestones after the
hardware STT path is verified.
