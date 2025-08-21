from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate, get_user_model
from django.core.mail import EmailMessage
from django.conf import settings

from .serializers import RegisterSerializer, LoginSerializer, ChatbotQuerySerializer, FeedbackSerializer
import os, json
import logging
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token


from authapp.models import ContactUs, Feedback
from django.core.mail import EmailMessage

# --- Feedback API ---
class FeedbackAPI(APIView):
    def post(self, request):
        serializer = FeedbackSerializer(data=request.data)
        if serializer.is_valid():
            feedback_obj = serializer.save()
            # Send email to team
            subject = f"New Feedback from {feedback_obj.name}"
            message = f"""
            Name: {feedback_obj.name}
            Rating: {feedback_obj.rating}
            Feedback: {feedback_obj.feedback}
            """
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email='Indeed Inspiring Infotech <aartilahane013@gmail.com>',
                to=['iipt.aiml@gmail.com'],
            )
            email.send(fail_silently=False)
            return Response({'message': 'Feedback submitted successfully!'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
from .serializers import  ForgotPasswordSerializer, RegisterSerializer, LoginSerializer, ResetPasswordSerializer, User
from .serializers import ChatbotQuerySerializer
from .indeed_bot import *
from .gmtt_bot import *
from .common_utils import *

from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from .models import ChatbotConversation
from .serializers import ChatbotConversationSerializer
import os
import json


from authapp.indeed_bot import get_indeed_response
from authapp.gmtt_bot import get_gmtt_response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.authtoken.models import Token
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator


User = get_user_model()

# indeed_kb = load_knowledge_base('indeed_knowledge.json')
# gmtt_kb = load_knowledge_base('gmtt_knowledge.json')


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
        Name: {name}
        Email: {email}
        Message: {message}
        """

        email_to_team = EmailMessage(
            subject=subject_to_team,
            body=message_to_team,
            from_email='Indeed Inspiring Infotech <aartilahane013@gmail.com>',
            to=['iipt.aiml@gmail.com'],
        )
        email_to_team.send(fail_silently=False)

        subject_to_user = "Thank You for Reaching Out"
        message_to_user = f"""
        Hi {name},
        Thank you for contacting us. We'll get back to you shortly.
        """

        email_to_user = EmailMessage(
            subject=subject_to_user,
            body=message_to_user,
            from_email='Indeed Inspiring Infotech <aartilahane013@gmail.com>',
            to=[email],
        )
        email_to_user.send(fail_silently=False)

        return Response({'message': 'Message sent successfully!'}, status=status.HTTP_200_OK)


# Register API
class RegisterAPI(APIView):
    def post(self, request):
        # Map frontend firstName/lastName to backend first_name/last_name
        data = request.data.copy()
        serializer = RegisterSerializer(data=data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            username = serializer.validated_data['username']
            firstName = serializer.validated_data.get('firstName', '')
            lastName = serializer.validated_data.get('lastName', '')

            if User.objects.filter(email=email).exists():
                return Response({'error': 'Email is already registered'}, status=status.HTTP_400_BAD_REQUEST)
            if User.objects.filter(username=username).exists():
                return Response({'error': 'Username is already taken'}, status=status.HTTP_400_BAD_REQUEST)

            user = serializer.save(firstName=firstName, lastName=lastName)
            return Response({'message': 'User registered successfully'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class LoginAPI(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            identifier = serializer.validated_data['username']  # can be username or email
            password = serializer.validated_data['password']

            user = None
            # Try to get user by username
            try:
                user_obj = User.objects.get(username=identifier)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                # Try to get user by email
                try:
                    user_obj = User.objects.get(email=identifier)
                    user = authenticate(username=user_obj.username, password=password)
                except User.DoesNotExist:
                    user = None

            if user is not None:
                token, created = Token.objects.get_or_create(user=user)
                return Response({
                    'message': 'Login successful',
                    'token': token.key,
                    'firstName': user.firstName,  # for frontend compatibility
                    'lastName': user.lastName,    # for frontend compatibility
                    'email': user.email,
                }, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Invalid username/email or password'}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    

# @method_decorator(csrf_exempt, name='dispatch')
# class InterviewBotAPI(APIView):
#     def post(self, request):
#         user_input = request.data.get('input')
#         if not user_input:
#             return Response({'error': 'Input is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
#         ngrok_url = "https://e6b4-35-199-148-56.ngrok-free.app/"  # Your bot endpoint
        
#         try:
#             # Forward user input to ngrok bot
#             ngrok_response = requests.post(ngrok_url, json={'input': user_input}, timeout=10)
#             ngrok_response.raise_for_status()
            
#             # Parse response from bot
#             bot_reply = ngrok_response.json()
            
#             # Return bot's response to user
#             return Response({'response': bot_reply}, status=status.HTTP_200_OK)
        
#         except requests.RequestException as e:
#             return Response({'error': 'Failed to connect to interview bot.', 'details': str(e)}, status=status.HTTP_502_BAD_GATEWAY)


# Import your mistral helper functions
from .interiewbot import mistral_generate, generate_next_question, evaluate_answer, resume_summary, job_desc_text, get_level_prompt, follow_up_instruction

# Keep interview state in memory (can later move to DB/Redis)
conversation_history = {}
qa_log = {}

@method_decorator(csrf_exempt, name='dispatch')
class InterviewBotAPI(APIView):
    def post(self, request):
        user_id = request.data.get("user_id", "default")  # identify user (session, token, etc.)
        user_input = request.data.get("input")

        if not user_input:
            return Response({"error": "Input is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Initialize conversation if new
        if user_id not in conversation_history:
            conversation_history[user_id] = f"""
            You are a friendly and professional interview bot.
            Job Description: {job_desc_text}
            Candidate Resume Summary: {resume_summary}
            Rules:
            - One question at a time.
            - {get_level_prompt("easy")}
            - {follow_up_instruction}

            Interviewer: Hello, thank you for joining the interview today. Let's begin. 
            Can you briefly introduce yourself?
            """
            qa_log[user_id] = []

            first_question = "Hello, thank you for joining the interview today. Let's begin. Can you briefly introduce yourself?"
            return Response({"response": first_question}, status=status.HTTP_200_OK)

        # Add candidate's answer
        conversation_history[user_id] += f"\nCandidate: {user_input}"

        # Store answer for evaluation later
        if qa_log[user_id]:
            qa_log[user_id][-1]["answer"] = user_input

        # Generate next question
        try:
            question = generate_next_question(conversation_history[user_id])
            conversation_history[user_id] += f"\nInterviewer: {question}"

            # Save Q for evaluation
            qa_log[user_id].append({"question": question, "answer": None})

            return Response({"response": question}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": "Interview bot failed.", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ChatbotAPI(APIView):
    def post(self, request):
        serializer = ChatbotQuerySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        query = serializer.validated_data['query']
        chatbot_type = serializer.validated_data['chatbot_type']
        user_identifier = serializer.validated_data['user']

        # Try to fetch user by username, then by email, then by first_name
        user = None
        try:
            user = User.objects.get(username=user_identifier)
        except User.DoesNotExist:
            try:
                user = User.objects.get(email=user_identifier)
            except User.DoesNotExist:
                try:
                    user = User.objects.get(firstName=user_identifier)
                except User.DoesNotExist:
                    return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            if chatbot_type == 'indeed':
                response = get_indeed_response(query, user=user)
            else:
                response = get_gmtt_response(query, user=user)
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


class ChatHistoryAPI(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        chatbot_type = request.query_params.get('chatbot_type')
        user = request.user

        if not chatbot_type:
            return Response({'error': 'chatbot_type is required'}, status=400)

        conversations = ChatbotConversation.objects.filter(
            user=user, 
            chatbot_type=chatbot_type
        ).order_by('-timestamp')
        
        serializer = ChatbotConversationSerializer(conversations, many=True)
        return Response(serializer.data)

            
            
class ForgotPasswordAPI(APIView):
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                reset_url = f"{settings.FRONTEND_URL}reset-password/{uid}/{token}/"

                send_mail(
                    "Reset Your Password",
                    f"Click the link below to reset your password:\n{reset_url}",
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                )
                return Response({"message": "Password reset link sent to your email."}, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response({"error": "User with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# class ResetPasswordAPI(APIView):
#     def post(self, request, uidb64, token):
#         serializer = ResetPasswordSerializer(data=request.data)
#         if serializer.is_valid():
#             try:
#                 uid = force_str(urlsafe_base64_decode(uidb64))
#                 user = User.objects.get(pk=uid)
#                 if default_token_generator.check_token(user, token):
#                     user.set_password(serializer.validated_data['new_password'])
#                     user.save()
#                     return Response({"message": "Password has been reset successfully."}, status=status.HTTP_200_OK)
#                 else:
#                     return Response({"error": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)
#             except Exception as e:
#                 return Response({"error": "Something went wrong."}, status=status.HTTP_400_BAD_REQUEST)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        
class ResetPasswordAPI(APIView):
    def post(self, request, uidb64, token):
        print("🔧 Incoming password reset request")
        print("📦 Data received:", request.data)
        print("🔐 UID (base64):", uidb64)
        print("🔐 Token:", token)

        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            try:
                uid = force_str(urlsafe_base64_decode(uidb64))
                print("✅ Decoded UID:", uid)

                user = User.objects.get(pk=uid)
                print("👤 User found:", user.email)

                if default_token_generator.check_token(user, token):
                    print("🔓 Token is valid. Proceeding to reset password.")
                    user.set_password(serializer.validated_data['new_password'])
                    user.save()
                    print("✅ Password reset successful.")
                    return Response({"message": "Password has been reset successfully."}, status=status.HTTP_200_OK)
                else:
                    print("❌ Invalid or expired token.")
                    return Response({"error": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

            except Exception as e:
                print("❌ Exception occurred:", str(e))
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            print("❌ Serializer invalid:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# class CheckResetTokenAPI(APIView):
#     def get(self, request, uidb64, token):
#         try:
#             uid = force_str(urlsafe_base64_decode(uidb64))
#             user = User.objects.get(pk=uid)
            
#             if default_token_generator.check_token(user, token):
#                 return Response({"valid": True}, status=status.HTTP_200_OK)
#             return Response({"valid": False}, status=status.HTTP_400_BAD_REQUEST)
            
#         except (TypeError, ValueError, OverflowError, User.DoesNotExist):
#             return Response({"valid": False}, status=status.HTTP_400_BAD_REQUEST)


class CheckResetTokenAPI(APIView):
    def get(self, request, uidb64, token):
        print("🔍 Checking reset token")
        print("🔐 Received UID (base64):", uidb64)
        print("🔐 Received token:", token)
        
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            print("🔢 Decoded UID:", uid)
            
            user = User.objects.get(pk=uid)
            print("👤 User found:", user.email)
            
            token_valid = default_token_generator.check_token(user, token)
            print("✅ Token valid:", token_valid)
            
            return Response({"valid": token_valid}, status=status.HTTP_200_OK)
            
        except (TypeError, ValueError, OverflowError) as e:
            print("❌ Decoding error:", str(e))
            return Response({"valid": False, "error": "Invalid UID format"}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            print("❌ User not found")
            return Response({"valid": False, "error": "User not found"}, status=status.HTTP_400_BAD_REQUEST)
