"""Brain handlers for streamed PCM audio and conversation generation."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import perf_counter

from loguru import logger
from pydantic import ValidationError
from websockets.asyncio.server import ServerConnection

from brain.services.audio_buffer import AudioBufferService, AudioSessionError
from brain.services.conversation import ConversationLogger, ConversationMemory, TranscriptFilter
from brain.services.character import CharacterService
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
    character_service: CharacterService | None = None,
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
            raw_duration = len(pcm) / float(metadata.sample_rate * 2)
            if transcript_filter is not None and raw_duration < transcript_filter.min_duration_seconds:
                logger.warning(
                    "Audio rejected before Whisper: reason=too_short, duration={:.2f}s, bytes={}",
                    raw_duration,
                    len(pcm),
                )
                await websocket.send(
                    TranscriptPayload(
                        session_id=payload.session_id,
                        text="",
                        language=metadata.language,
                        duration_seconds=raw_duration,
                    ).to_message().to_json()
                )
                return

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
                accepted, reason = transcript_filter.accept(
                    websocket,
                    transcript_text,
                    duration_seconds=result.duration_seconds,
                    rms=result.rms,
                    no_speech_probability=result.no_speech_probability,
                    average_log_probability=result.average_log_probability,
                )
                if not accepted:
                    logger.warning(
                        "Transcript rejected: reason={}, text={!r}, duration={:.2f}s, rms={:.4f}, no_speech={}, avg_logprob={}",
                        reason,
                        transcript_text,
                        result.duration_seconds,
                        result.rms,
                        result.no_speech_probability,
                        result.average_log_probability,
                    )
                    return
            elif not transcript_text:
                logger.info("Empty transcript; skipping LLM generation")
                return

            if llm is not None and speech is not None:
                local_reply = (
                    character_service.local_reply(transcript_text)
                    if character_service is not None
                    else None
                )
                if local_reply is not None:
                    reply_text = local_reply
                    reply_model = "nobi-character"
                    logger.info("Local character response selected: text={!r}", reply_text)
                else:
                    history = memory.messages(websocket) if memory is not None else None
                    llm_started = perf_counter()
                    if not hasattr(llm, "stream"):
                        llm_result = await llm.generate(transcript_text, history=history)
                        reply_text = (
                            character_service.polish(llm_result.text)
                            if character_service is not None
                            else llm_result.text
                        )
                        reply_model = llm_result.model
                        emotion = (
                            emotion_service.classify(transcript_text, reply_text)
                            if emotion_service is not None
                            else None
                        )
                        await speech.say(
                            reply_text,
                            emotion=emotion.value if emotion is not None else None,
                        )
                        logger.info(
                            "LLM compatibility path completed: model={}, seconds={:.2f}",
                            reply_model,
                            perf_counter() - llm_started,
                        )
                        llm_stream = None
                    else:
                        llm_stream = await llm.stream(transcript_text, history=history)

                    def polish_segment(segment: str) -> str:
                        return (
                            character_service.polish(segment)
                            if character_service is not None
                            else segment.strip()
                        )

                    def segment_emotion(segment: str) -> str | None:
                        if emotion_service is None:
                            return None
                        return emotion_service.classify(transcript_text, segment).value

                    if llm_stream is not None:
                        tts_started = perf_counter()
                        _, reply_text = await speech.say_stream(
                            llm_stream,
                            emotion_for=segment_emotion,
                            transform=polish_segment,
                        )
                        tts_seconds = perf_counter() - tts_started
                        llm_seconds = perf_counter() - llm_started
                        reply_model = llm_stream.model
                        logger.info(
                            "LLM streaming response completed: model={}, text={!r}",
                            reply_model,
                            reply_text,
                        )
                        logger.info(
                            "First-token latency: {}; LLM stream total: {:.2f}s",
                            f"{llm_stream.first_token_seconds:.2f}s"
                            if llm_stream.first_token_seconds is not None
                            else "unknown",
                            llm_stream.completed_seconds or llm_seconds,
                        )
                        logger.info(
                            "Streaming speech latency: {:.2f}s; total pipeline: {:.2f}s",
                            tts_seconds,
                            perf_counter() - pipeline_started,
                        )

                if local_reply is not None:
                    emotion = (
                        emotion_service.classify(transcript_text, reply_text)
                        if emotion_service is not None
                        else None
                    )
                    logger.info("Speech emotion selected: {}", emotion or "neutral")
                    tts_started = perf_counter()
                    await speech.say(
                        reply_text,
                        emotion=emotion.value if emotion is not None else None,
                    )
                    tts_seconds = perf_counter() - tts_started
                    logger.info(
                        "Speech latency: {:.2f}s; total pipeline: {:.2f}s",
                        tts_seconds,
                        perf_counter() - pipeline_started,
                    )
                if memory is not None:
                    memory.add(websocket, transcript_text, reply_text)
                    logger.info("Conversation memory updated: turns={}", len(memory.messages(websocket)) // 2)
                if conversation_logger is not None:
                    await conversation_logger.append(
                        transcript_text,
                        reply_text,
                        reply_model,
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
