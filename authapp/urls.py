# from django.urls import path
# from .views import (
#     RegisterAPI, 
#     LoginAPI, 
#     ContactUsAPI,
#     ChatbotAPI,
# )

# urlpatterns = [
#     path('register/', RegisterAPI.as_view(), name='register'),
#     path('login/', LoginAPI.as_view(), name='login'),
#     path('contact/', ContactUsAPI.as_view(), name='contact'),
#     path('indeed-chat/', ChatbotAPI.as_view(), name='indeed_chat'),
#     # path('gmtt-chat/', ChatbotAPI.as_view(), name='gmtt_chat'),
# ]

from django.urls import path
from .views import (
    RegisterAPI, 
    LoginAPI, 
    ContactUsAPI,
    ChatbotAPI,
)

urlpatterns = [
    path('register/', RegisterAPI.as_view(), name='register'),
    path('login/', LoginAPI.as_view(), name='login'),
    path('contact/', ContactUsAPI.as_view(), name='contact'),
    path('indeed-chat/<str:bot_name>/', ChatbotAPI.as_view(), name='indeed_chat'),  # <-- fix here
    # path('gmtt-chat/', ChatbotAPI.as_view(), name='gmtt_chat'),
]