import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ChatbotConversation
from .chatbot_utils import get_indeed_response, get_safety_response
# Change this import
# from authapp.models import ChatbotConversation  # Instead of .models


User = get_user_model()

class ChatbotConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = None
        self.chatbot_type = None
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data=None, bytes_data=None):
        try:
            if bytes_data:
                # Handle binary data (voice input)
                await self.handle_voice_input(bytes_data)
            else:
                # Handle text data
                data = json.loads(text_data)
                await self.handle_text_input(data)
        except Exception as e:
            await self.send_error(str(e))

    async def handle_text_input(self, data):
        message_type = data.get('type')
        
        if message_type == 'auth':
            await self.handle_authentication(data)
        elif message_type == 'query':
            await self.handle_chatbot_query(data)
        else:
            await self.send_error('Invalid message type')

    async def handle_authentication(self, data):
        try:
            user_identifier = data.get('user')
            self.chatbot_type = data.get('chatbot_type', 'indeed')
            
            # Get user from database
            self.user = await self.get_user(user_identifier)
            
            if not self.user:
                await self.send_error('User not found')
                return
            
            await self.send(json.dumps({
                'type': 'auth',
                'status': 'success',
                'message': 'Authentication successful'
            }))
        except Exception as e:
            await self.send_error(f'Authentication failed: {str(e)}')

    async def handle_chatbot_query(self, data):
        if not self.user:
            await self.send_error('Not authenticated')
            return

        query = data.get('query')
        if not query:
            await self.send_error('Empty query')
            return

        try:
            if self.chatbot_type == 'indeed':
                response = await database_sync_to_async(get_indeed_response)(
                    query, 
                    user=self.user
                )
            else:
                response = await database_sync_to_async(get_safety_response)(
                    query, 
                    user=self.user
                )

            await self.send(json.dumps({
                'type': 'response',
                'response': response,
                'chatbot': self.chatbot_type
            }))
        except Exception as e:
            await self.send_error(f'Query processing failed: {str(e)}')

    async def handle_voice_input(self, bytes_data):
        if not self.user:
            await self.send_error('Not authenticated')
            return

        try:
            # Here you would typically send the audio to a speech recognition service
            # For now, we'll just echo back a placeholder response
            await self.send(json.dumps({
                'type': 'voice_processing',
                'status': 'received',
                'message': 'Voice input received (processing not implemented)'
            }))
        except Exception as e:
            await self.send_error(f'Voice processing failed: {str(e)}')

    async def send_error(self, message):
        await self.send(json.dumps({
            'type': 'error',
            'message': message
        }))

    @database_sync_to_async
    def get_user(self, user_identifier):
        try:
            return User.objects.get(username=user_identifier)
        except User.DoesNotExist:
            try:
                return User.objects.get(email=user_identifier)
            except User.DoesNotExist:
                return None