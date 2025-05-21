from rest_framework import serializers # type: ignore
from django.contrib.auth import get_user_model # type: ignore
from django.contrib.auth.hashers import make_password # type: ignore


User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'password']
    
    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class ChatbotQuerySerializer(serializers.Serializer):
    query = serializers.CharField(required=True)
    chatbot_type = serializers.ChoiceField(
        choices=[('indeed', 'Indeed Chatbot'), ('gmtt', 'Give Me Trees Chatbot')],
        required=True
    )
