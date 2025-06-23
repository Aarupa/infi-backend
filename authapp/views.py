# views.py
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.core.mail import EmailMessage

from authapp.models import ContactUs
from .serializers import  ForgotPasswordSerializer, RegisterSerializer, LoginSerializer, ResetPasswordSerializer, User
from .serializers import ChatbotQuerySerializer
from .indeed_bot import *
from .gmtt_bot import *
from .common_utils import *

from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str

import os
import json

# Initialize knowledge bases
script_dir = os.path.dirname(os.path.abspath(__file__))
json_dir = os.path.join(script_dir, 'json_files')

def load_knowledge_base(file_name):
    file_path = os.path.join(json_dir, file_name)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {'faqs': []}

indeed_kb = load_knowledge_base('indeed_knowledge.json')
gmtt_kb = load_knowledge_base('gmtt_knowledge.json')

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
                return Response({'message': 'Login successful'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class ContactUsAPI(APIView):
    def post(self, request):
        name = request.data.get('name')
        email = request.data.get('email')
        message = request.data.get('message')

        if not name or not email or not message:
            return Response({'error': 'All fields are required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # ✅ Save to database
        ContactUs.objects.create(name=name, email=email, message=message)

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
            
            
class ForgotPasswordAPI(APIView):
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                reset_url = f"http://your-frontend-url/reset-password/{uid}/{token}/"

                send_mail(
                    "Reset Your Password",
                    f"Click the link below to reset your password:\n{reset_url}",
                    "no-reply@yourdomain.com",
                    [email],
                )
                return Response({"message": "Password reset link sent to your email."}, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response({"error": "User with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResetPasswordAPI(APIView):
    def post(self, request, uidb64, token):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            try:
                uid = force_str(urlsafe_base64_decode(uidb64))
                user = User.objects.get(pk=uid)
                if default_token_generator.check_token(user, token):
                    user.set_password(serializer.validated_data['new_password'])
                    user.save()
                    return Response({"message": "Password has been reset successfully."}, status=status.HTTP_200_OK)
                else:
                    return Response({"error": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({"error": "Something went wrong."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            
# class ContactUsAPIView(APIView):

#     def get(self, request):
#         contacts = ContactUs.objects.all().order_by('-created_at')
#         serializer = ContactUsSerializer(contacts, many=True)
#         return Response(serializer.data, status=status.HTTP_200_OK)

#     def post(self, request):
#         serializer = ContactUsSerializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             return Response({"message": "Your message has been received."}, status=status.HTTP_201_CREATED)
#         else:
#             print(serializer.errors)  # Add this for debugging
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
