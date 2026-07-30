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

# RobotOS B2.0 — Cartoon Voice Engine

B2.0 gives the Raspberry Pi Node a configurable voice personality while preserving the stable B1.9 conversation pipeline.

Default profile: `cartoon`.

Install the optional post-processing dependency on Raspberry Pi:

```bash
sudo apt update
sudo apt install -y sox
```

Recommended configuration:

```bash
export ROBOTOS_VOICE_PROFILE=cartoon
export ROBOTOS_VOICE_AUTO_EXPRESSION=1
export ROBOTOS_VOICE_POSTPROCESS=1
```

Available profiles are `classic`, `cartoon`, `energetic`, `kid`, and `calm`.

Fine tuning is optional:

```bash
export ROBOTOS_VOICE_PITCH=180
export ROBOTOS_VOICE_TEMPO=1.06
export ROBOTOS_VOICE_GAIN_DB=0.5
```

When override values are omitted, each profile uses its own safe defaults. If SoX is missing, RobotOS logs a warning and continues with Piper prosody only.
