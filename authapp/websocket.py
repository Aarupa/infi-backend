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
        msg_type = data.get("type")

        if msg_type == "user_message":
            user_input = data.get("message", "")
            username = data.get("user", "guest")

            from .gmtt_bot import get_gmtt_response
            response = get_gmtt_response(user_input, user=username)

            await self.send(text_data=json.dumps({
                "type": "bot_response",
                "message": response,
            }))

        elif msg_type == "bargein":
            # Optional: log or handle interruption logic
            print(f"[WS] Barge-in received from user: {data.get('user')}")
            # You can add any interruption handling here
            await self.send(text_data=json.dumps({
                "type": "ack",
                "message": "Barge-in received"
            }))

        else:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": f"Unknown message type: {msg_type}"
            }))
