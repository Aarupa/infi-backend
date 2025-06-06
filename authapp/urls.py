from django.urls import path
from .views import (
    RegisterAPI, 
    LoginAPI, 
    ContactUsAPI,
    ChatbotAPI,
    InterviewBotAPI,
)

urlpatterns = [
    path('register/', RegisterAPI.as_view(), name='register'),
    path('login/', LoginAPI.as_view(), name='login'),
    path('contact/', ContactUsAPI.as_view(), name='contact'),
    path('indeed-chat/', ChatbotAPI.as_view(), name='indeed_chat'),
    # path('gmtt-chat/', ChatbotAPI.as_view(), name='gmtt_chat'),
    # path('api/interview-bot/', InterviewBotAPI.as_view(), name='interview-bot'),
    path('interview-bot/', InterviewBotAPI.as_view(), name='interview-bot')
]