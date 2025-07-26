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
                source = data.get("source", "nirankari")  # default to nirankari

                # Get text response from appropriate bot
                text_response = await self.get_text_response(user_input, username, source)
                
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

    async def get_text_response(self, user_input, username, source):
        """Route to appropriate response generator"""
        if source == "gmtt":
            from .gmtt_bot import get_gmtt_response
            return await sync_to_async(get_gmtt_response)(user_input, user=username)
        else:
            from .nirankari_bot import get_nirankari_response
            return await sync_to_async(get_nirankari_response)(user_input, user=username)

    async def stream_audio(self, text):
        try:
            lang = 'en'  # Optional: Auto-detect language
            polly_service = AWSPollyService()
            result = await sync_to_async(polly_service.synthesize_speech)(text, lang, save_to_file=False)
            
            if result['success']:
                await self.send(text_data=json.dumps({
                    "type": "audio_start",
                    "format": "mp3"
                }))
                
                await self.send(bytes_data=result['audio_stream'])

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
