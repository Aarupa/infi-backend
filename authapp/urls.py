from django.urls import path
from .views import (
    ChatbotAPI,
    ForgotPasswordAPI,
    RegisterAPI, 
    LoginAPI, 
    ContactUsAPI,
    ResetPasswordAPI,
    
)

urlpatterns = [
    path('register/', RegisterAPI.as_view(), name='register'),
    path('login/', LoginAPI.as_view(), name='login'),
    path('contact/', ContactUsAPI.as_view(), name='contact_us'),
    path('indeed-chat/', ChatbotAPI.as_view(), name='indeed_chat'),
    # path('gmtt-chat/', ChatbotAPI.as_view(), name='gmtt_chat'),
    
    # path('contact/', ContactUsAPI.as_view(), name='contact_us'),
    
    path('forgot-password/', ForgotPasswordAPI.as_view(), name='forgot-password'),
    path('reset-password/<uidb64>/<token>/', ResetPasswordAPI.as_view(), name='reset-password'),
]