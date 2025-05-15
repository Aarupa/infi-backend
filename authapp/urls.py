from django.urls import path
from .views import ContactUsAPI, RegisterAPI, LoginAPI

urlpatterns = [
    path('api/register/', RegisterAPI.as_view(), name='register'),
    path('api/login/', LoginAPI.as_view(), name='login'),
    path('api/contact/', ContactUsAPI.as_view(), name='contact_us'),
]

