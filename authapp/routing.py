# authapp/routing.py
from django.urls import re_path
from .websocket import ChatBotConsumer

websocket_urlpatterns = [
    re_path(r'ws/chatbot/$', ChatBotConsumer.as_asgi()),
]
