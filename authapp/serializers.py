

# --- Imports (organized, no duplicates) ---
import re
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from .models import ChatbotConversation, ContactUs, Register
from authapp.models import Feedback



User = get_user_model()




class RegisterSerializer(serializers.ModelSerializer):
    firstName = serializers.CharField(required=True)
    lastName = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'firstName', 'lastName']

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
        # Map camelCase to model fields
        validated_data['firstName'] = validated_data.pop('firstName')
        validated_data['lastName'] = validated_data.pop('lastName')
        return super().create(validated_data)



class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)


class ChatbotQuerySerializer(serializers.Serializer):
    query = serializers.CharField()
    chatbot_type = serializers.ChoiceField(choices=['indeed', 'gmtt'])
    user = serializers.CharField(required=True)



# --- ChatbotConversation Serializer (corrected) ---
class ChatbotConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotConversation
        fields = ['id', 'user', 'chatbot_type', 'session_id', 'query', 'response', 'timestamp']
        read_only_fields = ['id', 'timestamp']

# --- Feedback Serializer ---
class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ['id', 'name', 'rating', 'feedback', 'created_at']
        read_only_fields = ['id', 'created_at']

    


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

