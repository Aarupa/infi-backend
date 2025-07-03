from django.urls import re_path
from . import chatbot_websocket

websocket_urlpatterns = [
    re_path(r'ws/chatbot/$', chatbot_websocket.ChatbotConsumer.as_asgi()),
]