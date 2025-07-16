# authapp/routing.py
from django.urls import re_path
from .websocket import ChatBotConsumer, ESP32Consumer

websocket_urlpatterns = [
    re_path(r'ws/chatbot/$', ChatBotConsumer.as_asgi()),
    re_path(r'ws/esp32/$', ESP32Consumer.as_asgi()),  # New WebSocket path for ESP32
]
