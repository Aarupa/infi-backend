# views.py
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.core.mail import EmailMessage
from .serializers import RegisterSerializer, LoginSerializer
from .serializers import ChatbotQuerySerializer
from .chatbot_logic import (
    get_indeed_response,
    get_gmtt_response,
    save_conversation_to_file,
)

class RegisterAPI(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'User registered successfully'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginAPI(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = authenticate(
                username=serializer.validated_data['username'],
                password=serializer.validated_data['password']
            )
            if user:
                return Response({
                    'message': 'Login successful'
                }, status=status.HTTP_200_OK)
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ContactUsAPI(APIView):
    def post(self, request):
        name = request.data.get('name')
        email = request.data.get('email')
        message = request.data.get('message')

        if not name or not email or not message:
            return Response({'error': 'All fields are required.'}, status=status.HTTP_400_BAD_REQUEST)

        subject_to_team = f"New Request from {name}"
        message_to_team = f"""
        You have received a new inquiry:

        Name: {name}
        Email: {email}
        Message:
        {message}

        Regards,
        Indeed Inspiring Infotech Website
        """

        email_to_team = EmailMessage(
            subject=subject_to_team,
            body=message_to_team,
            from_email='Indeed Inspiring Infotech <aartilahane013@gmail.com>',
            to=['iipt.aiml@gmail.com'],
        )
        email_to_team.send(fail_silently=False)

        subject_to_user = "Thank You for Reaching Out to Indeed Inspiring Infotech"
        message_to_user = f"""
        Hi {name},

        Thank you for contacting Indeed Inspiring Infotech. We've received your message and will get back to you soon.

        Best Regards,  
        Indeed Inspiring Infotech Team
        """

        email_to_user = EmailMessage(
            subject=subject_to_user,
            body=message_to_user,
            from_email='Indeed Inspiring Infotech <aartilahane013@gmail.com>',
            to=[email],
        )
        email_to_user.send(fail_silently=False)

        return Response({'message': 'Your message has been sent successfully!'}, status=status.HTTP_200_OK)

class ChatbotAPI(APIView):
    def post(self, request):
        serializer = ChatbotQuerySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        query = serializer.validated_data['query']
        chatbot_type = serializer.validated_data['chatbot_type']
        
        try:
            if chatbot_type == 'indeed':
                response = get_indeed_response(query)
            else:
                response = get_gmtt_response(query)
            
            # Save conversation if needed
            save_conversation_to_file(query, response)
            
            return Response({
                'response': response,
                'chatbot': chatbot_type
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logging.error(f"Chatbot error: {str(e)}")
            return Response({
                'error': 'An error occurred while processing your request',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)