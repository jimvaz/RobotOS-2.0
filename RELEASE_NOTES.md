# RobotOS 2.0 — B1.4.4

## Summary

B1.4.4 introduces the Brain message-routing layer. Validated messages are now
forwarded by `BrainServer` to a registry-based `MessageRouter`, while HELLO and
HEARTBEAT behavior lives in dedicated handlers.

## Changes

- Implemented an asynchronous handler registry in `brain/router.py`.
- Added `brain/handlers/hello.py` and `brain/handlers/heartbeat.py`.
- Added duplicate-registration protection and safe handler removal.
- Refactored `BrainServer` to build the default routing table and dispatch messages.
- Added unit tests for routing, missing handlers, duplicate registration, HELLO,
  and HEARTBEAT responses.

## Compatibility

No wire-protocol or configuration changes are required. Existing HELLO,
HEARTBEAT, validation-error, connection, and lifecycle behavior is preserved.

## Validation

Run from the project root:

```powershell
pytest
python -m compileall brain node shared tests
```

## Next milestone

B1.5 will connect the SPEECH event to the Node Piper TTS pipeline for the first
end-to-end spoken response.
