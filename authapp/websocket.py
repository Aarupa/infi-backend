import json
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

                # Get text response
                text_response = await self.get_text_response(user_input, username)
                
                # Send text response immediately
                await self.send(text_data=json.dumps({
                    "type": "text_response",
                    "message": text_response
                }))

                # Generate and stream audio
                await self.stream_audio(text_response)

        except Exception as e:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": f"Processing error: {str(e)}"
            }))

    async def get_text_response(self, user_input, username):
        """Get response using your existing GMTT logic"""
        from .gmtt_bot import get_gmtt_response
        return await sync_to_async(get_gmtt_response)(user_input, user=username)

    async def stream_audio(self, text):
        """Stream audio chunks via WebSocket"""
        try:
            # Detect language (simplified - use your actual detection logic)
            lang = 'en'  # Default, implement your detection

            # Create or get polly_service instance
            polly_service = AWSPollyService()

            # Get audio synchronously without saving to file
            result = await sync_to_async(polly_service.synthesize_speech)(text, lang, save_to_file=False)
            
            if result['success']:
                # Send audio start marker
                await self.send(text_data=json.dumps({
                    "type": "audio_start",
                    "format": "mp3"
                }))
                
                # Send binary audio data in chunks
                chunk_size = 4096  # Adjust based on your needs
                audio_data = result['audio_stream']
                
                for i in range(0, len(audio_data), chunk_size):
                    chunk = audio_data[i:i+chunk_size]
                    await self.send(bytes_data=chunk)
                
                # Send audio end marker
                await self.send(text_data=json.dumps({
                    "type": "audio_end"
                }))
            else:
                raise Exception(result['error'])

        except Exception as e:
            await self.send(text_data=json.dumps({
                "type": "audio_error",
                "message": f"Audio generation failed: {str(e)}"
            }))