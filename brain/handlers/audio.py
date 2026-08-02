"""Brain handlers for streamed PCM audio and conversation generation."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import perf_counter

from loguru import logger
from pydantic import ValidationError
from websockets.asyncio.server import ServerConnection

from brain.services.audio_buffer import AudioBufferService, AudioSessionError
from brain.services.conversation import ConversationLogger, ConversationMemory, TranscriptFilter
from brain.services.emotion import EmotionService
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
    memory: ConversationMemory | None = None,
    transcript_filter: TranscriptFilter | None = None,
    conversation_logger: ConversationLogger | None = None,
    emotion_service: EmotionService | None = None,
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
            pipeline_started = perf_counter()
            stt_started = perf_counter()
            result = await whisper.transcribe(
                pcm,
                sample_rate=metadata.sample_rate,
                language=metadata.language,
            )
            stt_seconds = perf_counter() - stt_started
            transcript_text = result.text.strip()
            transcript = TranscriptPayload(
                session_id=payload.session_id,
                text=transcript_text,
                language=result.language,
                duration_seconds=result.duration_seconds,
            )
            await websocket.send(transcript.to_message().to_json())
            logger.info("Transcript: {!r} (stt={:.2f}s, audio={:.2f}s)", transcript_text, stt_seconds, result.duration_seconds)

            if transcript_filter is not None:
                accepted, reason = transcript_filter.accept(websocket, transcript_text)
                if not accepted:
                    logger.info("Transcript skipped: reason={}, text={!r}", reason, transcript_text)
                    return
            elif not transcript_text:
                logger.info("Empty transcript; skipping LLM generation")
                return

            if llm is not None and speech is not None:
                history = memory.messages(websocket) if memory is not None else None
                llm_started = perf_counter()
                llm_result = await llm.generate(transcript_text, history=history)
                llm_seconds = perf_counter() - llm_started
                logger.info(
                    "LLM response generated: model={}, text={!r}",
                    llm_result.model,
                    llm_result.text,
                )
                logger.info("LLM latency: {:.2f}s", llm_seconds)
                emotion = (
                    emotion_service.classify(transcript_text, llm_result.text)
                    if emotion_service is not None
                    else None
                )
                logger.info("Speech emotion selected: {}", emotion or "neutral")
                tts_started = perf_counter()
                await speech.say(
                    llm_result.text,
                    emotion=emotion.value if emotion is not None else None,
                )
                tts_seconds = perf_counter() - tts_started
                logger.info("Speech latency: {:.2f}s; total pipeline: {:.2f}s", tts_seconds, perf_counter() - pipeline_started)
                if memory is not None:
                    memory.add(websocket, transcript_text, llm_result.text)
                    logger.info("Conversation memory updated: turns={}", len(memory.messages(websocket)) // 2)
                if conversation_logger is not None:
                    await conversation_logger.append(
                        transcript_text,
                        llm_result.text,
                        llm_result.model,
                    )
        except (ValidationError, ValueError, AudioSessionError) as exc:
            await websocket.send(_error("invalid_audio_end", str(exc), message.id).to_json())
        except WhisperError as exc:
            logger.error("Whisper failed: {}", exc)
            await websocket.send(_error("whisper_failed", str(exc), message.id).to_json())
        except LLMError as exc:
            logger.error("Ollama failed: {}", exc)
            await websocket.send(_error("llm_failed", str(exc), message.id).to_json())

    return handle_start, handle_chunk, handle_end
