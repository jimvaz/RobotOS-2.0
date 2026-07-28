# Changelog

## 2.0.0-alpha.1 — Sprint B1.1

- Added RobotOS protocol v1 constants.
- Added validated shared message model.
- Added message serialization and deserialization.
- Added common message and event enumerations.
- Added shared Loguru configuration.
- Added protocol and model unit tests.


## B1.4.1
- Added initial brain/connection_manager.py scaffold.


## B1.4.2
- Added RELEASE_NOTES.md
- Added ConnectionManager scaffold.


## B1.4.3

- Integrated `ConnectionManager` into `BrainServer`.
- Removed direct client-set ownership from the server.
- Added immutable connection snapshots and collection helpers.
- Added connection-manager unit tests.
- Preserved existing protocol behavior.

## B1.4.4

- Added a registry-based asynchronous `MessageRouter`.
- Added dedicated HELLO and HEARTBEAT handlers.
- Reduced `BrainServer` to validation, connection lifecycle, and dispatch duties.
- Added router and handler unit tests.
- Preserved protocol and WebSocket behavior.

## B1.5.1

- Added validated shared `SpeechPayload` messages.
- Added the Brain `SpeechService` for broadcasting speech to connected nodes.
- Added a Brain SPEECH handler that validates and forwards manual commands.
- Added Node message routing and a SPEECH logging handler.
- Updated the manual `send_speech` command to use the shared payload model.
- Added speech pipeline unit tests.

## B1.5.2

- Connected the Node SPEECH handler to the Piper text-to-speech engine.
- Added a background speech queue so WebSocket message reception remains responsive.
- Guaranteed sequential playback and prevented overlapping speech requests.
- Added graceful Piper, voice-model, and audio-player validation.
- Added resilient error handling so one failed synthesis does not stop later speech.
- Added unit tests for handler integration, ordering, failure recovery, blank input,
  and Piper configuration validation.
