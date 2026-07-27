# RobotOS 2.0 — B1.5.1

## Summary

B1.5.1 introduces the first functional speech-event path from the Brain to the
Node. A manual SPEECH command is validated by the Brain, forwarded to connected
nodes, routed by the Node, and logged by the Node speech handler.

Piper playback is intentionally deferred to B1.5.2 so networking and message
routing can be verified independently from audio configuration.

## Changes

- Added `shared.speech.SpeechPayload` with text and optional emotion validation.
- Added `brain.services.SpeechService` for delivery to active Node connections.
- Added the Brain SPEECH handler and registered it in the default routing table.
- Added `node.router.NodeMessageRouter`.
- Added `node.handlers.speech.handle_speech` for validated speech logging.
- Updated `brain/send_speech.py` to build messages through `SpeechPayload`.
- Added unit tests for validation, serialization, broadcast, sender exclusion,
  Brain forwarding, error responses, and Node routing.

## Expected manual flow

1. Start the Brain WebSocket server.
2. Start the Raspberry Pi Node client.
3. Run `python -m brain.send_speech` on the Brain computer.
4. Enter Greek text.
5. Confirm that the Node log displays `[SPEECH] <text>`.

## Validation

Run from the project root:

```powershell
pytest
python -m compileall brain node shared tests
```

## Next milestone

B1.5.2 will connect the Node SPEECH handler to the existing Piper TTS service so
the received text is synthesized and played through the Raspberry Pi speakers.
