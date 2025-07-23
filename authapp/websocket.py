import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from authapp.polly_service import AWSPollyService

class ChatBotConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data["type"] == "user_message":
                user_input = data["message"]
                username = data.get("user", "guest")

                # ✅ Get bot response (text)
                text_response = await self.get_text_response(user_input, username)

                # ✅ Stream response text in chunks
                await self.stream_text_response(text_response)

                # ✅ Stream audio after text
                await self.stream_audio(text_response)

        except Exception as e:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": f"Processing error: {str(e)}"
            }))

    async def get_text_response(self, user_input, username):
        """Calls your bot logic (synchronously)"""
        from .gmtt_bot import get_gmtt_response
        return await sync_to_async(get_gmtt_response)(user_input, user=username)

    async def stream_text_response(self, text):
        """Break text into chunks and send them one-by-one"""
        words = text.split()
        chunk = ""
        max_words = 6  # Adjust for chunk size

        for i, word in enumerate(words):
            chunk += word + " "
            # Send every few words or at the end
            if (i + 1) % max_words == 0 or i == len(words) - 1:
                await self.send(text_data=json.dumps({
                    "type": "text_stream",
                    "message": chunk.strip()
                }))
                chunk = ""
                await asyncio.sleep(0.2)  # Delay for real-time feel

    async def stream_audio(self, text):
        """Stream Polly-generated audio chunks to frontend"""
        try:
            lang = 'en'
            polly_service = AWSPollyService()
            result = await sync_to_async(polly_service.synthesize_speech_stream)(text, lang)

            if result['success']:
                audio_stream = result['stream']

                # Notify frontend that audio stream is starting
                await self.send(text_data=json.dumps({
                    "type": "audio_start",
                    "format": "mp3"
                }))

                # Stream audio in chunks
                chunk_size = 2048
                while True:
                    chunk = await sync_to_async(audio_stream.read)(chunk_size)
                    if not chunk:
                        break
                    await self.send(bytes_data=chunk)

                # Notify frontend that audio stream has ended
                await self.send(text_data=json.dumps({
                    "type": "audio_end"
                }))
            else:
                raise Exception(result['error'])

        except Exception as e:
            await self.send(text_data=json.dumps({
                "type": "audio_error",
                "message": f"Audio streaming error: {str(e)}"
            }))
