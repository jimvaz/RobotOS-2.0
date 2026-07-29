"""Brain handlers for streamed PCM audio and Whisper transcription."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from loguru import logger
from pydantic import ValidationError
from websockets.asyncio.server import ServerConnection

from brain.services.audio_buffer import AudioBufferService, AudioSessionError
from brain.services.llm import LLMError, LLMService
from brain.services.speech import SpeechService
from brain.services.whisper import WhisperError, WhisperService
from shared.audio import AudioChunkPayload, AudioEndPayload, AudioStartPayload, TranscriptPayload
from shared.models import Message
from shared.protocol import MessageType

AudioHandler = Callable[[ServerConnection, Message], Awaitable[None]]


def _error(code: str, text: str, reply_to: str) -> Message:
    return Message(
        type=MessageType.ERROR,
        payload={"code": code, "message": text, "reply_to": reply_to},
    )


def create_audio_handlers(
    buffers: AudioBufferService,
    whisper: WhisperService,
    llm: LLMService | None = None,
    speech: SpeechService | None = None,
) -> tuple[AudioHandler, AudioHandler, AudioHandler]:
    async def handle_start(websocket: ServerConnection, message: Message) -> None:
        try:
            payload = AudioStartPayload.from_message(message)
            buffers.start(websocket, payload)
            logger.info("Audio session started: {}", payload.session_id)
        except (ValidationError, ValueError, AudioSessionError) as exc:
            await websocket.send(_error("invalid_audio_start", str(exc), message.id).to_json())

    async def handle_chunk(websocket: ServerConnection, message: Message) -> None:
        try:
            payload = AudioChunkPayload.from_message(message)
            buffers.append(websocket, payload)
        except (ValidationError, ValueError, AudioSessionError) as exc:
            await websocket.send(_error("invalid_audio_chunk", str(exc), message.id).to_json())

    async def handle_end(websocket: ServerConnection, message: Message) -> None:
        try:
            payload = AudioEndPayload.from_message(message)
            metadata, pcm = buffers.finish(websocket, payload)
            logger.info(
                "Audio session completed: session={}, bytes={}",
                payload.session_id,
                len(pcm),
            )
            result = await whisper.transcribe(
                pcm,
                sample_rate=metadata.sample_rate,
                language=metadata.language,
            )
            transcript = TranscriptPayload(
                session_id=payload.session_id,
                text=result.text,
                language=result.language,
                duration_seconds=result.duration_seconds,
            )
            await websocket.send(transcript.to_message().to_json())
            logger.info("Transcript: '{}'", result.text)

            if not result.text.strip():
                logger.info("Empty transcript; skipping LLM generation")
                return
            if llm is not None and speech is not None:
                llm_result = await llm.generate(result.text)
                logger.info(
                    "LLM response generated: model={}, text={!r}",
                    llm_result.model,
                    llm_result.text,
                )
                await speech.say(llm_result.text)
        except (ValidationError, ValueError, AudioSessionError) as exc:
            await websocket.send(_error("invalid_audio_end", str(exc), message.id).to_json())
        except WhisperError as exc:
            logger.error("Whisper failed: {}", exc)
            await websocket.send(_error("whisper_failed", str(exc), message.id).to_json())
        except LLMError as exc:
            logger.error("Ollama failed: {}", exc)
            await websocket.send(_error("llm_failed", str(exc), message.id).to_json())

    return handle_start, handle_chunk, handle_end
