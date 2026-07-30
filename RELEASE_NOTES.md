# RobotOS 2.0 B1.9 Release Notes

Version: `2.0.0-alpha.5`

B1.9 adds short-term conversational continuity and transcript quality controls while preserving the verified B1.8 turn-taking pipeline.

## Added

- Per-connection bounded conversation memory (`ROBOTOS_MAX_HISTORY`, default 10 turns).
- Previous user/assistant messages sent to Ollama with each new request.
- Near-duplicate transcript filter with configurable time window and similarity threshold.
- UTF-8 JSONL conversation log (`logs/conversations.jsonl` by default).
- Dedicated tests for memory bounds, duplicate filtering, history payloads, and conversation logging.

## Changed

- Ollama temperature reduced from `0.4` to `0.2` for steadier replies.
- Greek system prompt improved for context-aware, brief, natural TTS responses.
- Empty and duplicate transcripts are logged and skipped before LLM generation.
- Conversation state is cleared when a Node disconnects.

## Preserved

- `think: false` Ollama compatibility fix.
- B1.8 microphone pause/resume during Piper playback.
- Existing WebSocket protocol and Raspberry Pi configuration.

## Validation

- `46 passed`
- `compileall` passed
- ZIP integrity checked
