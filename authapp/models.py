from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

class CustomUser(AbstractUser):
    # Add extra fields here if needed
    pass
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

# models.py

class ChatbotConversation(models.Model):
    CHATBOT_CHOICES = (
        ('indeed', 'Indeed'),
        ('gmtt', 'GMTT'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    chatbot_type = models.CharField(max_length=10, choices=CHATBOT_CHOICES)
    session_id = models.CharField(max_length=100)  # Add this line
    query = models.TextField()
    response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.chatbot_type} - {self.timestamp}"
class Register(models.Model):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)  # Store hashed passwords

    def __str__(self):
        return self.username

class ContactUs(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Contact from {self.name} at {self.email}"

