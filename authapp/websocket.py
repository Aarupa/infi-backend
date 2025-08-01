import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

logger = logging.getLogger("chatbot")

class ChatBotConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        logger.info("WebSocket connection established")

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected with code {close_code}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            msg_type = data.get("type")

            if msg_type == "user_message":
                user_input = data.get("message", "")
                username = data.get("user", "guest")
                source = data.get("source", "nirankari")  # Default to nirankari

                logger.debug(f"Received message: '{user_input}' from '{username}', source: '{source}'")

                # Get response
                text_response = await self.get_text_response(user_input, username, source)

                # Send response
                await self.send(json.dumps({
                    "type": "text_response",
                    "message": text_response
                }))

                # Uncomment if Polly audio is needed
                # await self.stream_audio(text_response)

            else:
                logger.warning(f"Unsupported message type: {msg_type}")
                await self.send(json.dumps({
                    "type": "error",
                    "message": "Unsupported message type."
                }))

        except Exception as e:
            logger.exception("Error processing message")
            await self.send(json.dumps({
                "type": "error",
                "message": f"Processing error: {str(e)}"
            }))

    async def get_text_response(self, user_input, username, source):
        """Route message to appropriate chatbot logic"""
        if source == "gmtt":
            from .gmtt_bot import get_gmtt_response
            return await sync_to_async(get_gmtt_response)(user_input, user=username)
        else:
            from .nirankari_bot import get_nirankari_response
            return await sync_to_async(get_nirankari_response)(user_input, user=username)

    # Optional: Text-to-speech streaming (AWS Polly)
    # async def stream_audio(self, text):
    #     try:
    #         from authapp.polly_service import AWSPollyService
    #         polly_service = AWSPollyService()
    #         result = await sync_to_async(polly_service.synthesize_speech)(text, lang='en', save_to_file=False)
            
    #         if result['success']:
    #             await self.send(json.dumps({
    #                 "type": "audio_start",
    #                 "format": "mp3"
    #             }))
    #             await self.send(bytes_data=result['audio_stream'])
    #             await self.send(json.dumps({
    #                 "type": "audio_end"
    #             }))
    #         else:
    #             raise Exception(result['error'])

    #     except Exception as e:
    #         logger.exception("Audio generation failed")
    #         await self.send(json.dumps({
    #             "type": "audio_error",
    #             "message": f"Audio generation failed: {str(e)}"
    #         }))
