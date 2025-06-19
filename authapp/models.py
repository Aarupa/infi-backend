from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    # Add extra fields here if needed
    pass

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class ChatbotConversation(models.Model):
    CHATBOT_CHOICES = [
        ('indeed', 'Indeed Bot'),
        ('gmtt', 'GMTT Bot'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    chatbot_type = models.CharField(max_length=10, choices=CHATBOT_CHOICES)
    query = models.TextField()
    response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.chatbot_type} - {self.timestamp}"