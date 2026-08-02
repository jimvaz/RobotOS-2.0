"""RobotOS Brain WebSocket server."""

from __future__ import annotations

import asyncio

from loguru import logger
from pydantic import ValidationError
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from brain.config import CONFIG
from brain.connection_manager import ConnectionManager
from brain.handlers import (
    create_audio_handlers,
    create_speech_handler,
    create_speech_interrupt_handler,
    handle_heartbeat,
    handle_hello,
)
from brain.router import MessageRouter
from brain.services import (
    AudioBufferService,
    ConversationLogger,
    ConversationMemory,
    EmotionService,
    LLMService,
    SpeechService,
    TranscriptFilter,
    WhisperService,
)
from brain.services.tts import ChatterboxTTS
from shared.models import Message
from shared.protocol import MessageType


class BrainServer:
    """Accept connections and delegate validated messages to the router."""

    def __init__(self, router: MessageRouter | None = None) -> None:
        self.connections = ConnectionManager()
        tts_backend = None
        if CONFIG.tts_engine == "chatterbox":
            tts_backend = ChatterboxTTS(
                device=CONFIG.chatterbox_device,
                language_id=CONFIG.chatterbox_language,
                reference_audio=CONFIG.chatterbox_reference_audio,
                startup_timeout=CONFIG.chatterbox_startup_timeout,
                synthesis_timeout=CONFIG.chatterbox_synthesis_timeout,
            )
        elif CONFIG.tts_engine != "piper":
            logger.warning("Unknown TTS engine %r; using Piper", CONFIG.tts_engine)
        self.speech = SpeechService(
            self.connections,
            backend=tts_backend,
            fallback_to_node=CONFIG.tts_fallback_to_node,
            chunk_size=CONFIG.audio_playback_chunk_size,
        )
        logger.info("TTS engine configured: {}", CONFIG.tts_engine)
        self.audio_buffers = AudioBufferService(
            max_audio_bytes=CONFIG.max_audio_seconds * 16000 * 2
        )
        self.whisper = WhisperService(
            model_name=CONFIG.whisper_model,
            device=CONFIG.whisper_device,
            compute_type=CONFIG.whisper_compute_type,
            beam_size=CONFIG.whisper_beam_size,
            best_of=CONFIG.whisper_best_of,
            vad_filter=CONFIG.whisper_vad_filter,
        )
        self.memory = ConversationMemory(max_turns=CONFIG.max_history)
        self.transcript_filter = TranscriptFilter(
            dedup_seconds=CONFIG.transcript_dedup_seconds,
            similarity_threshold=CONFIG.transcript_similarity_threshold,
            min_duration_seconds=CONFIG.min_audio_seconds,
            min_rms=CONFIG.min_audio_rms,
            max_no_speech_probability=CONFIG.whisper_max_no_speech_prob,
            min_average_log_probability=CONFIG.whisper_min_avg_log_prob,
        )
        self.conversation_logger = ConversationLogger(CONFIG.conversation_log_path)
        self.emotion = EmotionService() if CONFIG.emotion_engine_enabled else None
        self.llm = LLMService(
            model=CONFIG.ollama_model,
            base_url=CONFIG.ollama_url,
            timeout_seconds=CONFIG.ollama_timeout_seconds,
            system_prompt=CONFIG.system_prompt,
            num_predict=CONFIG.ollama_num_predict,
            num_ctx=CONFIG.ollama_num_ctx,
        )
        self.router = router or self._create_default_router()

    def _create_default_router(self) -> MessageRouter:
        """Build the standard Brain protocol routing table."""

        router = MessageRouter()
        router.register(MessageType.HELLO, handle_hello)
        router.register(MessageType.HEARTBEAT, handle_heartbeat)
        router.register(MessageType.SPEECH, create_speech_handler(self.speech))
        router.register(
            MessageType.SPEECH_INTERRUPT,
            create_speech_interrupt_handler(self.speech),
        )
        audio_start, audio_chunk, audio_end = create_audio_handlers(
            self.audio_buffers,
            self.whisper,
            self.llm,
            self.speech,
            self.memory,
            self.transcript_filter,
            self.conversation_logger,
            self.emotion,
        )
        router.register(MessageType.AUDIO_START, audio_start)
        router.register(MessageType.AUDIO_CHUNK, audio_chunk)
        router.register(MessageType.AUDIO_END, audio_end)
        return router

    async def handle_client(self, websocket: ServerConnection) -> None:
        """Handle one connected RobotOS node."""

        remote_address = websocket.remote_address
        await self.connections.connect(websocket)
        logger.info("Node connected: {}", remote_address)

        try:
            async for raw_message in websocket:
                await self.handle_message(websocket, raw_message)
        except ConnectionClosed as exc:
            logger.warning(
                "Node connection closed: code={}, reason={}",
                exc.code,
                exc.reason or "none",
            )
        except Exception:
            logger.exception("Unexpected client error")
        finally:
            self.audio_buffers.discard_connection(websocket)
            self.memory.clear(websocket)
            self.transcript_filter.clear(websocket)
            await self.connections.disconnect(websocket)
            logger.info("Node disconnected: {}", remote_address)

    async def handle_message(
        self,
        websocket: ServerConnection,
        raw_message: str | bytes,
    ) -> None:
        """Validate an incoming protocol message and dispatch it."""

        try:
            message = Message.from_json(raw_message)
        except ValidationError as exc:
            logger.warning("Invalid protocol message: {}", exc)
            error_message = Message(
                type=MessageType.ERROR,
                payload={
                    "code": "invalid_message",
                    "message": "The received message is invalid.",
                },
            )
            await websocket.send(error_message.to_json())
            return

        logger.info("Message received: type={}, id={}", message.type, message.id)
        await self.router.dispatch(websocket, message)

    async def _preload_services(self) -> None:
        if not CONFIG.preload_models:
            return
        logger.info("Preloading Whisper and TTS services...")
        results = await asyncio.gather(
            self.whisper.preload(),
            self.speech.preload(),
            return_exceptions=True,
        )
        for name, result in zip(("Whisper", "TTS"), results):
            if isinstance(result, Exception):
                logger.warning("{} preload failed: {}", name, result)
            else:
                logger.info("{} preload complete", name)

    async def start(self) -> None:
        """Start the WebSocket server and wait indefinitely."""

        await self._preload_services()
        logger.info("Starting WebSocket server on ws://{}:{}", CONFIG.host, CONFIG.port)
        try:
            async with serve(
                self.handle_client,
                CONFIG.host,
                CONFIG.port,
                max_size=2 * 1024 * 1024,
            ):
                logger.info("Waiting for RobotOS nodes...")
                await asyncio.Future()
        finally:
            await self.speech.close()

    def run(self) -> None:
        """Run the Brain server."""

        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            logger.info("Brain server stopped by user")
