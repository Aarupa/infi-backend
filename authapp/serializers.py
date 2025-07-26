
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
import re

from rest_framework import serializers # type: ignore
from django.contrib.auth import get_user_model # type: ignore
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import ChatbotConversation

from authapp.models import ContactUs, Register # type: ignore



User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def validate_email(self, value):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", value):
            raise serializers.ValidationError("Enter a valid email address.")
        return value

    def validate_password(self, value):
        if len(value) < 6:
            raise serializers.ValidationError("Password must be at least 6 characters long.")
        return value

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)

class ChatbotQuerySerializer(serializers.Serializer):

    query = serializers.CharField()
    chatbot_type = serializers.ChoiceField(choices=['indeed', 'gmtt','nirankari'])
    user = serializers.CharField(required=True)  # Add this line

class ChatbotConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotConversation
        fields = ['id', 'chatbot_type', 'query', 'response', 'timestamp']

    query = serializers.CharField(required=True)
    chatbot_type = serializers.ChoiceField(
        choices=[('indeed', 'Indeed Chatbot'), ('gmtt', 'Give Me Trees Chatbot')],
        required=True
    )
    user = serializers.CharField(required=True)  # Add this line


from rest_framework import serializers
from .models import ChatbotConversation

class ChatbotConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactUs
        fields = '__all__'
        read_only_fields = ['created_at']

    
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        
        if len(data['new_password']) < 6:
            raise serializers.ValidationError("Password must be at least 6 characters long.")
        
        return data

