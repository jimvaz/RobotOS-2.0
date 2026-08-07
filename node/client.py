"""RobotOS Node WebSocket client."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from loguru import logger
from pydantic import ValidationError
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from node.audio import AudioRecorder, AudioRecorderError, AudioStreamer, RecorderConfig
from node.config import CONFIG
from node.handlers import create_speech_handler, handle_transcript
from node.handlers.audio_playback import create_audio_playback_handler, create_audio_stream_handlers
from node.router import NodeMessageRouter
from node.tts import PiperTTS, SpeechQueue, VoiceEngine
from node.tts.audio_player import AudioPlaybackQueue
from shared.barge_in import SpeechInterruptPayload
from shared.audio_playback import AudioPlaybackFinishedPayload
from shared.models import Message
from shared.protocol import MessageType
from shared.version import PROTOCOL_VERSION, ROBOTOS_VERSION


class NodeClient:
    """Connects the Raspberry Pi Node to the RobotOS Brain."""

    def __init__(self) -> None:
        self.running = True
        self._barge_in_task: asyncio.Task[None] | None = None
        self._barge_in_capture_active = False
        self._speech_active = False
        self.websocket: ClientConnection | None = None
        self.router = NodeMessageRouter()
        self.piper = PiperTTS(
            executable=CONFIG.piper_executable,
            model_path=CONFIG.piper_model,
            audio_player=CONFIG.audio_player,
            sox_executable=CONFIG.sox_executable,
            postprocess_enabled=CONFIG.voice_postprocess_enabled,
        )
        self.voice_engine = VoiceEngine(
            self.piper,
            profile=CONFIG.voice_profile,
            auto_expression=CONFIG.voice_auto_expression,
            pitch_override=CONFIG.voice_pitch_override,
            tempo_override=CONFIG.voice_tempo_override,
            gain_override=CONFIG.voice_gain_override,
        )
        self.speech_queue = SpeechQueue(
            self.voice_engine,
            on_speech_start=self._pause_microphone_for_speech,
            on_speech_end=self._resume_microphone_after_speech,
        )
        self.audio_playback_queue = AudioPlaybackQueue(
            CONFIG.audio_player,
            on_start=self._pause_microphone_for_speech,
            on_end=self._resume_microphone_after_speech,
            on_playback_finished=self._send_playback_finished,
        )
        self.audio_recorder = AudioRecorder(
            RecorderConfig(
                sample_rate=CONFIG.microphone_sample_rate,
                speech_threshold=CONFIG.microphone_threshold,
                silence_ms=CONFIG.microphone_silence_ms,
                pre_buffer_ms=CONFIG.microphone_pre_buffer_ms,
                max_utterance_seconds=CONFIG.microphone_max_seconds,
            )
        )
        self.audio_streamer = AudioStreamer(self.send_message)
        self.router.register(
            MessageType.SPEECH,
            create_speech_handler(self.speech_queue),
        )
        self.router.register(
            MessageType.AUDIO_PLAYBACK,
            create_audio_playback_handler(self.audio_playback_queue),
        )
        playback_start, playback_chunk, playback_end, playback_cancel = create_audio_stream_handlers(
            self.audio_playback_queue
        )
        self.router.register(MessageType.AUDIO_PLAYBACK_START, playback_start)
        self.router.register(MessageType.AUDIO_PLAYBACK_CHUNK, playback_chunk)
        self.router.register(MessageType.AUDIO_PLAYBACK_END, playback_end)
        self.router.register(MessageType.AUDIO_PLAYBACK_CANCEL, playback_cancel)
        self.router.register(MessageType.TRANSCRIPT, handle_transcript)

    async def _send_playback_finished(self, speech_id: str) -> None:
        """ACK only after aplay has consumed the final speech segment."""
        await self.send_message(AudioPlaybackFinishedPayload(speech_id).to_message())
        logger.info("Playback finished ACK sent: speech={}", speech_id)

    async def _pause_microphone_for_speech(self) -> None:
        """Pause normal capture and start the optional barge-in monitor."""

        self._speech_active = True
        self.audio_recorder.pause()
        self.audio_recorder.discard_pending()
        logger.info("MIC locked for Nobi speech")
        if (
            CONFIG.barge_in_enabled
            and CONFIG.microphone_enabled
            and (self._barge_in_task is None or self._barge_in_task.done())
        ):
            self._barge_in_task = asyncio.create_task(
                self._barge_in_loop(), name="node-barge-in"
            )

    async def _resume_microphone_after_speech(self) -> None:
        """Resume normal capture after playback unless barge-in owns the mic."""

        current = asyncio.current_task()
        task = self._barge_in_task
        if task is not None and task is not current and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if self._barge_in_capture_active:
            return
        await asyncio.sleep(CONFIG.microphone_resume_delay)
        self.audio_recorder.discard_pending()
        self._speech_active = False
        self.audio_recorder.resume()
        logger.info("MIC resumed after {:.0f} ms cooldown", CONFIG.microphone_resume_delay * 1000)

    async def _barge_in_loop(self) -> None:
        """Detect a user utterance during playback and take the conversational turn."""

        await asyncio.sleep(CONFIG.barge_in_grace_ms / 1000)
        while self.running and self.audio_playback_queue.is_playing:
            pcm = await self.audio_recorder.record_barge_in(
                speech_threshold=CONFIG.barge_in_threshold,
                silence_ms=CONFIG.barge_in_silence_ms,
                pre_buffer_ms=CONFIG.barge_in_pre_buffer_ms,
                max_utterance_seconds=CONFIG.barge_in_max_seconds,
            )
            if not pcm:
                if self.audio_playback_queue.is_playing:
                    await asyncio.sleep(0.05)
                    continue
                return

            self._barge_in_capture_active = True
            logger.info("Barge-in detected: bytes={}", len(pcm))
            try:
                await self.send_message(SpeechInterruptPayload().to_message())
                await self.audio_playback_queue.interrupt("user barge-in")
                session_id = await self.audio_streamer.stream(
                    pcm,
                    sample_rate=CONFIG.microphone_sample_rate,
                    language=CONFIG.language,
                )
                logger.info(
                    "Barge-in utterance sent: session={}, bytes={}",
                    session_id,
                    len(pcm),
                )
            except (ConnectionClosed, RuntimeError):
                return
            finally:
                self._barge_in_capture_active = False
                self.audio_recorder.resume()
                logger.info("MIC resumed after barge-in")
            return

    async def send_message(self, message: Message) -> None:
        """Send a validated RobotOS protocol message."""

        if self.websocket is None:
            raise RuntimeError("Node is not connected to the Brain")

        await self.websocket.send(message.to_json())

        logger.debug(
            "Message sent: type={}, id={}",
            message.type,
            message.id,
        )

    async def perform_handshake(self) -> None:
        """Send HELLO and wait for acceptance from the Brain."""

        hello = Message(
            type=MessageType.HELLO,
            payload={
                "node_id": CONFIG.node_id,
                "node_name": CONFIG.node_name,
                "robotos_version": ROBOTOS_VERSION,
                "protocol_version": PROTOCOL_VERSION,
                "capabilities": [],
            },
        )

        await self.send_message(hello)
        logger.info("HELLO sent to Brain")

        if self.websocket is None:
            raise RuntimeError("Connection disappeared during handshake")

        raw_response = await asyncio.wait_for(
            self.websocket.recv(),
            timeout=CONFIG.handshake_timeout,
        )

        response = Message.from_json(raw_response)

        if response.type != MessageType.HELLO:
            raise RuntimeError(
                f"Expected HELLO response, received {response.type}"
            )

        if response.payload.get("status") != "accepted":
            raise RuntimeError(
                f"Brain rejected the Node: {response.payload}"
            )

        logger.info(
            "Handshake completed: brain={}, version={}, protocol={}",
            response.payload.get("brain_name", "unknown"),
            response.payload.get("robotos_version", "unknown"),
            response.payload.get("protocol_version", "unknown"),
        )

    async def heartbeat_loop(self) -> None:
        """Send regular heartbeat messages to the Brain."""

        while self.running:
            await asyncio.sleep(CONFIG.heartbeat_interval)

            heartbeat = Message(
                type=MessageType.HEARTBEAT,
                payload={
                    "node_id": CONFIG.node_id,
                    "status": "online",
                },
            )

            await self.send_message(heartbeat)
            logger.info("Heartbeat sent")

    async def receive_loop(self) -> None:
        """Receive and process messages from the Brain."""

        if self.websocket is None:
            raise RuntimeError("Node is not connected to the Brain")

        async for raw_message in self.websocket:
            try:
                message = Message.from_json(raw_message)
            except ValidationError as exc:
                logger.warning("Invalid message received from Brain: {}", exc)
                continue

            if message.type == MessageType.HEARTBEAT:
                logger.info(
                    "Heartbeat acknowledged: reply_to={}",
                    message.payload.get("reply_to", "unknown"),
                )
                continue

            if message.type == MessageType.ERROR:
                logger.error(
                    "Brain error: code={}, message={}",
                    message.payload.get("code", "unknown"),
                    message.payload.get("message", "No description"),
                )
                continue

            await self.router.dispatch(message)


    async def microphone_loop(self) -> None:
        """Capture utterances and stream them to the Brain while connected."""

        logger.info("Microphone listener enabled")
        while self.running and self.websocket is not None:
            try:
                await self.audio_recorder.wait_until_resumed()
                while self._barge_in_capture_active:
                    await asyncio.sleep(0.02)
                if not self.running or self.websocket is None:
                    return
                capture_generation = self.audio_recorder.generation
                pcm = await self.audio_recorder.record_utterance()
                if (
                    self._speech_active
                    or self.audio_recorder.paused
                    or capture_generation != self.audio_recorder.generation
                ):
                    logger.debug("Discarded stale microphone capture after state change")
                    continue
                if not pcm:
                    await asyncio.sleep(CONFIG.microphone_retry_delay)
                    continue
                session_id = await self.audio_streamer.stream(
                    pcm,
                    sample_rate=CONFIG.microphone_sample_rate,
                    language=CONFIG.language,
                )
                logger.info(
                    "Audio utterance sent: session={}, bytes={}",
                    session_id,
                    len(pcm),
                )
            except AudioRecorderError as exc:
                logger.error("Microphone capture failed: {}", exc)
                await asyncio.sleep(CONFIG.microphone_retry_delay)
            except (ConnectionClosed, RuntimeError):
                return

    async def run_connection(self) -> None:
        """Run one connection session."""

        logger.info("Connecting to {}", CONFIG.brain_uri)

        async with connect(
            CONFIG.brain_uri,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
            max_size=2 * 1024 * 1024,
        ) as websocket:
            self.websocket = websocket

            logger.info("Connected to RobotOS Brain")

            await self.perform_handshake()

            heartbeat_task = asyncio.create_task(
                self.heartbeat_loop(),
                name="node-heartbeat",
            )

            receive_task = asyncio.create_task(
                self.receive_loop(),
                name="node-receiver",
            )
            tasks = {heartbeat_task, receive_task}
            microphone_task: asyncio.Task[None] | None = None
            if CONFIG.microphone_enabled:
                microphone_task = asyncio.create_task(
                    self.microphone_loop(),
                    name="node-microphone",
                )
                tasks.add(microphone_task)

            try:
                done, pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_EXCEPTION,
                )

                for task in done:
                    exception = task.exception()
                    if exception is not None:
                        raise exception

            finally:
                for task in tasks:
                    task.cancel()

                for task in tasks:
                    with suppress(asyncio.CancelledError):
                        await task

                await self.audio_playback_queue.abort_stream("Brain connection ended")
                self.websocket = None

    async def start(self) -> None:
        """Connect continuously and automatically reconnect after failure."""

        self.speech_queue.start()
        self.audio_playback_queue.start()

        while self.running:
            try:
                await self.run_connection()

            except ConnectionClosed as exc:
                logger.warning(
                    "Brain connection closed: code={}, reason={}",
                    exc.code,
                    exc.reason or "none",
                )

            except ConnectionRefusedError:
                logger.warning(
                    "Brain is unavailable at {}",
                    CONFIG.brain_uri,
                )

            except asyncio.TimeoutError:
                logger.warning("Handshake with Brain timed out")

            except OSError as exc:
                logger.warning("Network connection failed: {}", exc)

            except Exception:
                logger.exception("Unexpected Node client error")

            if self.running:
                logger.info(
                    "Reconnecting in {} seconds...",
                    CONFIG.reconnect_delay,
                )
                await asyncio.sleep(CONFIG.reconnect_delay)

    async def shutdown(self) -> None:
        """Stop network activity and finish queued speech."""

        self.running = False
        if self._barge_in_task is not None:
            self._barge_in_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._barge_in_task
        await self.speech_queue.stop(drain=True)
        await self.audio_playback_queue.stop()

    def stop(self) -> None:
        """Request a graceful Node shutdown."""

        self.running = False

    def run(self) -> None:
        """Start the Node client."""

        async def runner() -> None:
            try:
                await self.start()
            finally:
                await self.shutdown()

        try:
            asyncio.run(runner())
        except KeyboardInterrupt:
            self.stop()
            logger.info("RobotOS Node stopped by user")
