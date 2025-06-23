from rest_framework import serializers # type: ignore
from django.contrib.auth import get_user_model # type: ignore
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password

from authapp.models import ContactUs, Register # type: ignore


User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)



class ChatbotQuerySerializer(serializers.Serializer):
    query = serializers.CharField(required=True)
    chatbot_type = serializers.ChoiceField(
        choices=[('indeed', 'Indeed Chatbot'), ('gmtt', 'Give Me Trees Chatbot')],
        required=True
    )
    
    
class ContactUsSerializer(serializers.Serializer):
    class Meta:
        model = ContactUs
        fields = '__all__'
        read_only_fields = ['created_at']
    
    # def validate_email(self, value):
    #     if not value:
    #         raise serializers.ValidationError("Email is required.")
    #     return value
    
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        validate_password(data['new_password'])
        return data
