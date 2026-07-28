"""Send one recorded PCM utterance to the RobotOS Brain."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

from shared.audio import AudioChunkPayload, AudioEndPayload, AudioStartPayload
from shared.models import Message

MessageSender = Callable[[Message], Awaitable[None]]


class AudioStreamer:
    def __init__(self, sender: MessageSender, chunk_bytes: int = 12_000) -> None:
        if chunk_bytes <= 0:
            raise ValueError("chunk_bytes must be positive")
        self.sender = sender
        self.chunk_bytes = chunk_bytes

    async def stream(
        self,
        pcm: bytes,
        *,
        sample_rate: int = 16000,
        language: str = "el",
        session_id: str | None = None,
    ) -> str:
        session_id = session_id or str(uuid4())
        await self.sender(
            AudioStartPayload(
                session_id=session_id,
                sample_rate=sample_rate,
                channels=1,
                sample_width=2,
                language=language,
            ).to_message()
        )

        chunk_count = 0
        for sequence, offset in enumerate(range(0, len(pcm), self.chunk_bytes)):
            chunk = pcm[offset : offset + self.chunk_bytes]
            await self.sender(
                AudioChunkPayload.from_bytes(session_id, sequence, chunk).to_message()
            )
            chunk_count += 1

        await self.sender(
            AudioEndPayload(session_id=session_id, chunk_count=chunk_count).to_message()
        )
        return session_id
