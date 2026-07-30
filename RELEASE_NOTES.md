# RobotOS 2.0.0-alpha.4 — B1.8

## Turn-taking and echo prevention

B1.8 prevents the Raspberry Pi microphone from capturing the robot's own Piper playback.

The Node now follows this lifecycle:

1. The user speaks and the utterance is sent to the Brain.
2. The Brain transcribes it with Whisper and generates a reply with Ollama.
3. When the `SPEECH` event reaches the Node, microphone capture is paused before Piper starts.
4. Any partial recording already in progress is discarded.
5. Piper synthesizes and plays the reply.
6. The Node waits for the configured acoustic settling delay, then resumes listening.

Default settling delay: `0.4` seconds.

Configure it with:

```bash
export ROBOTOS_MIC_RESUME_DELAY=0.4
```

Expected Node logs:

```text
MIC paused
[SPEECH] started: '...'
[SPEECH] finished: '...'
MIC resumed
```

## Also included

- The Ollama request explicitly sets `"think": false` so Qwen returns its final answer in `message.content`.
- Version updated to `2.0.0-alpha.4`.
- Tests cover microphone pause/resume and speech lifecycle hooks, including TTS failure recovery.
