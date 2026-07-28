# RobotOS 2.0 — B1.5.2

## Summary

B1.5.2 completes the first audible Brain-to-Node speech path. SPEECH messages are
validated by the Node, placed in a background queue, synthesized with Piper, and
played through the Raspberry Pi audio output.

The WebSocket receiver no longer waits for audio playback. Multiple messages are
spoken sequentially, and a failed synthesis or playback is logged without
stopping the queue.

## Changes

- Added `node.tts.SpeechQueue`, a single-worker asynchronous speech queue.
- Connected the Node SPEECH handler to the queue through dependency injection.
- Integrated `PiperTTS` into `NodeClient` using the existing Node configuration.
- Added checks for the Piper executable, ONNX voice model, and audio player.
- Added clear queued, speaking, completed, and failed logs.
- Added graceful Node shutdown that drains queued speech.
- Added tests using a fake speech engine; no Piper installation or speakers are
  required to run the test suite.

## Raspberry Pi configuration

The defaults are:

- Piper executable: `piper`
- Voice model: `/home/pi/robot/models/el_GR-rapunzelina-medium.onnx`
- Audio player: `aplay`

Override them when needed:

```bash
export PIPER_EXECUTABLE=/path/to/piper
export PIPER_MODEL=/path/to/el_GR-rapunzelina-medium.onnx
export AUDIO_PLAYER=aplay
```

The Piper model should normally have its matching JSON file beside it:

```text
el_GR-rapunzelina-medium.onnx
el_GR-rapunzelina-medium.onnx.json
```

## Manual validation

1. On the Raspberry Pi, verify Piper and ALSA independently.
2. Start the Brain server.
3. Start the Node client on the Raspberry Pi.
4. Run `python -m brain.send_speech` on the Brain computer.
5. Enter `Καλησπέρα!` and confirm that it is played through the Node speakers.

Expected Node logs:

```text
[SPEECH] queued: 'Καλησπέρα!'
[SPEECH] speaking: 'Καλησπέρα!'
Speech playback completed
[SPEECH] completed: 'Καλησπέρα!'
```

## Validation

```powershell
pytest
python -m compileall brain node shared tests
```

## Next milestone

B1.6 will introduce microphone capture and Whisper transcription so RobotOS can
hear spoken Greek before sending responses through the completed Piper path.
