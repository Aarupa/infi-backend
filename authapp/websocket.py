# authapp/websocket.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ChatBotConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data["type"] == "user_message":
            user_input = data["message"]
            username = data.get("user", "guest")

            # ✅ Lazy import to avoid ImproperlyConfigured error
            from .gmtt_bot import get_gmtt_response

            response = get_gmtt_response(user_input, user=username)
            await self.send(text_data=json.dumps({
                "type": "bot_response",
                "message": response,
            }))
