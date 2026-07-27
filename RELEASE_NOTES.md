# RobotOS 2.0 — B1.4.3

## Summary

B1.4.3 completes the first functional Brain connection-management refactor.
The `BrainServer` no longer owns or mutates a raw client set directly; all
connection registration and removal now pass through `ConnectionManager`.

## Changes

- Integrated `ConnectionManager` into `BrainServer`.
- Replaced direct `self.clients` set mutations with connection lifecycle calls.
- Added immutable connection snapshots, membership checks, length, and safe iteration.
- Added unit coverage for registration, removal, idempotent disconnect, and snapshot iteration.
- Preserved existing HELLO, HEARTBEAT, validation, and WebSocket behavior.

## Validation

Run from the project root:

```powershell
pytest
python -m compileall brain node shared tests
```

## Upgrade notes

No configuration or protocol changes are required. This release is an internal
architecture refactor and is intended to be behavior-compatible with B1.4.2.
