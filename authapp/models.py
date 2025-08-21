from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

class CustomUser(AbstractUser):
    firstName = models.CharField(max_length=150, blank=True, null=True)
    lastName = models.CharField(max_length=150, blank=True, null=True)
    # Remove first_name and last_name from AbstractUser
    first_name = None
    last_name = None
    
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

# --- Feedback Model ---
class Feedback(models.Model):
    name = models.CharField(max_length=100)
    rating = models.IntegerField()
    feedback = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback from {self.name} (Rating: {self.rating})"

