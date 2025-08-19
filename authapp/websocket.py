import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
import livekit
import asyncio
from livekit import rtc

logger = logging.getLogger("chatbot")

class ChatBotConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room = None
        self.audio_processor = None
        self.bot_identity = "gmtt-bot"
        self.livekit_url = "wss://gmttbot-m7dset78.livekit.cloud"
        self.livekit_token = ""  # Will be set from client

    async def connect(self):
        await self.accept()
        logger.info("WebSocket connection established")

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected with code {close_code}")
        if self.room:
            await self.cleanup_livekit()

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            msg_type = data.get("type")

            if msg_type == "user_message":
                # Handle text messages via WebSocket
                await self.handle_text_message(data)
            elif msg_type == "livekit_auth":
                # Initialize LiveKit connection
                await self.initialize_livekit(data)
            else:
                logger.warning(f"Unsupported message type: {msg_type}")
                await self.send_error("Unsupported message type")

        except Exception as e:
            logger.exception("Error processing message")
            await self.send_error(f"Processing error: {str(e)}")

    async def handle_text_message(self, data):
        """Process regular text messages"""
        user_input = data.get("message", "")
        username = data.get("user", "guest")
        source = data.get("source", "gmtt")

        logger.debug(f"Received text message: '{user_input}' from '{username}'")

        # Get response from your existing bot logic
        text_response = await self.get_text_response(user_input, username, source)

        # Send response via WebSocket
        await self.send(json.dumps({
            "type": "text_response",
            "message": text_response
        }))

    async def initialize_livekit(self, data):
        """Set up LiveKit connection for voice chat"""
        import sys
        self.livekit_token = data.get("token")
        if not self.livekit_token:
            await self.send_error("No LiveKit token provided")
            logger.info("[LiveKit][DEBUG][ERROR] No LiveKit token provided.")
            sys.stdout.flush()
            return

        try:
            # Create LiveKit room
            self.room = rtc.Room()
            logger.info(f"[LiveKit][DEBUG] LiveKit Room created: {self.room}")
            sys.stdout.flush()
            # Set up event handlers
            self.room.on("track_subscribed", self.on_track_subscribed)
            self.room.on("data_received", self.on_data_received)
            self.room.on("disconnected", self.on_disconnected)
            logger.info(f"[LiveKit][DEBUG] Event handlers registered on room: {self.room}")
            sys.stdout.flush()

            # Connect to LiveKit server
            await self.room.connect(
                self.livekit_url,
                self.livekit_token,
                publish_only="user-audio"  # Only publish audio from user
            )
            logger.info(f"[LiveKit][DEBUG] Connected to LiveKit server at {self.livekit_url} as bot.")
            logger.info(f"[LiveKit][DEBUG] Room state after connect: participants={getattr(self.room, 'participants', None)}")
            if hasattr(self.room, 'local_participant'):
                logger.info(f"[LiveKit][DEBUG] Local participant: {self.room.local_participant}")
                if hasattr(self.room.local_participant, 'audio_tracks'):
                    logger.info(f"[LiveKit][DEBUG] Local participant audio_tracks: {self.room.local_participant.audio_tracks}")
            if hasattr(self.room, 'participants'):
                logger.info(f"[LiveKit][DEBUG] Remote participants: {self.room.participants}")
            sys.stdout.flush()

            await self.send(json.dumps({
                "type": "livekit_ready",
                "message": "LiveKit connection established"
            }))

        except Exception as e:
            logger.error(f"LiveKit connection failed: {str(e)}")
            sys.stdout.flush()
            await self.send_error(f"Failed to connect to LiveKit: {str(e)}")

    async def on_track_subscribed(self, track, publication, participant):
        """Handle subscribed audio tracks from users"""
        if participant.identity == self.bot_identity:
            return  # Ignore our own tracks

        if track.kind == rtc.TrackKind.AUDIO:
            logger.info(f"Subscribed to audio track from {participant.identity}")
            
            # Set up audio processor
            self.audio_processor = AudioProcessor()
            await self.audio_processor.process_audio_stream(
                track,
                self.handle_voice_input
            )

    async def on_data_received(self, payload, participant, kind):
        """Handle data channel messages"""
        if participant.identity == self.bot_identity:
            return  # Ignore our own messages

        try:
            text = payload.decode('utf-8')
            logger.debug(f"Received data message: {text} from {participant.identity}")
            
            # Process the message (could be text input or commands)
            response = await self.get_text_response(text, participant.identity, "gmtt")
            
            # Send response back via LiveKit data channel
            await self.room.local_participant.publish_data(
                response.encode(),
                participant.sid,
                kind="bot_response"
            )

        except Exception as e:
            logger.error(f"Error processing data message: {str(e)}")

    async def handle_voice_input(self, audio_data):
        """Process incoming audio from user"""
        try:
            # Convert audio to text
            text = await self.transcribe_audio(audio_data)
            if not text:
                return

            logger.info(f"Transcribed text: {text}")
            
            # Get bot response
            response = await self.get_text_response(text, "voice_user", "gmtt")
            
            # Send text response via WebSocket (for UI)
            await self.send(json.dumps({
                "type": "text_response",
                "message": response
            }))
            
            # Convert text to speech and send via LiveKit
            await self.send_voice_response(response)

        except Exception as e:
            logger.error(f"Error processing voice input: {str(e)}")

    async def send_voice_response(self, text):
        """Convert text to speech and send via LiveKit"""
        if not self.room:
            return

        try:
            audio_data = await self.text_to_speech(text)
            if not audio_data:
                logger.error("No audio data generated for TTS.")
                return

            # LiveKit expects a track object, so use the SDK's PCM track creation
            # This is a placeholder; actual implementation may differ based on SDK
            audio_track = rtc.LocalAudioTrack.create_audio_track(
                "bot-voice",
                audio_data,
                sample_rate=16000,
                num_channels=1
            )
            await self.room.local_participant.publish_track(audio_track)
        except Exception as e:
            logger.error(f"Error sending voice response: {str(e)}")

    async def cleanup_livekit(self):
        """Clean up LiveKit resources"""
        try:
            if self.room:
                await self.room.disconnect()
                self.room = None
            
            if self.audio_processor:
                await self.audio_processor.cleanup()
                self.audio_processor = None

        except Exception as e:
            logger.error(f"Error cleaning up LiveKit: {str(e)}")

    async def send_error(self, message):
        """Send error message to client"""
        await self.send(json.dumps({
            "type": "error",
            "message": message
        }))

    # Your existing methods remain unchanged below
    async def get_text_response(self, user_input, username, source):
        """Route message to appropriate chatbot logic"""
        if source == "gmtt":
            from .gmtt_bot import get_gmtt_response
            return await sync_to_async(get_gmtt_response)(user_input, user=username)
        else:
            from .nirankari_bot import get_nirankari_response
            return await sync_to_async(get_nirankari_response)(user_input, user=username)

    async def transcribe_audio(self, audio_data):
        """Convert audio to text using Whisper (or your preferred service)"""
        import tempfile
        import os
        import torch
        import numpy as np
        import soundfile as sf
        try:
            # Assume audio_data is PCM bytes, 16-bit mono, 16kHz
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
                # Write WAV header and data
                sf.write(tmp, np.frombuffer(audio_data, dtype=np.int16), 16000, 'PCM_16')
                tmp_path = tmp.name

            # Use Whisper for transcription
            import whisper
            model = whisper.load_model('base')
            result = model.transcribe(tmp_path)
            os.remove(tmp_path)
            return result['text']
        except Exception as e:
            logger.error(f"Whisper transcription failed: {str(e)}")
            return ""

    async def text_to_speech(self, text):
        """Convert text to speech using AWS Polly"""
        import boto3
        import io
        polly = boto3.client('polly', region_name='us-west-2')
        try:
            response = polly.synthesize_speech(
                Text=text,
                OutputFormat='pcm',
                VoiceId='Kajal',
                Engine='neural',
                SampleRate='16000'
            )
            audio_stream = response['AudioStream'].read()
            return audio_stream
        except Exception as e:
            logger.error(f"Polly TTS failed: {str(e)}")
            return b""


class AudioProcessor:
    """Helper class to process incoming audio streams"""
    def __init__(self):
        self.active = False
        self.processing_task = None

    async def process_audio_stream(self, track, callback):
        """Process incoming audio frames"""
        self.active = True
        self.processing_task = asyncio.create_task(
            self._process_audio(track, callback)
        )

    async def _process_audio(self, track, callback):
        """Internal audio processing loop"""
        try:
            while self.active:
                frame = await track.read()
                if frame:
                    await callback(frame.data)
        except Exception as e:
            logger.error(f"Audio processing error: {str(e)}")

    async def cleanup(self):
        """Clean up audio processor"""
        self.active = False
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass