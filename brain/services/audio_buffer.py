"""In-memory PCM session assembly for incoming Node audio."""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.audio import AudioChunkPayload, AudioEndPayload, AudioStartPayload


class AudioSessionError(RuntimeError):
    """Raised when an audio stream violates session ordering or limits."""


@dataclass(slots=True)
class AudioSession:
    metadata: AudioStartPayload
    chunks: list[bytes] = field(default_factory=list)
    next_sequence: int = 0
    byte_count: int = 0

    @property
    def pcm(self) -> bytes:
        return b"".join(self.chunks)


class AudioBufferService:
    """Track active audio sessions and enforce bounded ordered streams."""

    def __init__(self, max_audio_bytes: int = 16_000 * 2 * 60) -> None:
        self.max_audio_bytes = max_audio_bytes
        self._sessions: dict[tuple[int, str], AudioSession] = {}

    @staticmethod
    def _key(connection: object, session_id: str) -> tuple[int, str]:
        return id(connection), session_id

    def start(self, connection: object, payload: AudioStartPayload) -> None:
        key = self._key(connection, payload.session_id)
        if key in self._sessions:
            raise AudioSessionError("Audio session already exists")
        self._sessions[key] = AudioSession(metadata=payload)

    def append(self, connection: object, payload: AudioChunkPayload) -> None:
        key = self._key(connection, payload.session_id)
        session = self._sessions.get(key)
        if session is None:
            raise AudioSessionError("Unknown audio session")
        if payload.sequence != session.next_sequence:
            raise AudioSessionError(
                f"Unexpected chunk sequence {payload.sequence}; expected {session.next_sequence}"
            )
        data = payload.decode()
        if session.byte_count + len(data) > self.max_audio_bytes:
            self._sessions.pop(key, None)
            raise AudioSessionError("Audio session exceeded maximum size")
        session.chunks.append(data)
        session.byte_count += len(data)
        session.next_sequence += 1

    def finish(
        self,
        connection: object,
        payload: AudioEndPayload,
    ) -> tuple[AudioStartPayload, bytes]:
        key = self._key(connection, payload.session_id)
        session = self._sessions.pop(key, None)
        if session is None:
            raise AudioSessionError("Unknown audio session")
        if payload.chunk_count != session.next_sequence:
            raise AudioSessionError(
                f"Chunk count {payload.chunk_count} does not match received {session.next_sequence}"
            )
        return session.metadata, session.pcm

    def discard_connection(self, connection: object) -> None:
        connection_id = id(connection)
        for key in [key for key in self._sessions if key[0] == connection_id]:
            self._sessions.pop(key, None)
