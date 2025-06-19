from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate, get_user_model
from django.core.mail import EmailMessage
from .serializers import RegisterSerializer, LoginSerializer, ChatbotQuerySerializer
import os, json
import logging
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token



from authapp.indeed_bot import get_indeed_response
from authapp.gmtt_bot import get_gmtt_response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

User = get_user_model()

# Contact Us API
class ContactUsAPI(APIView):
    def post(self, request):
        name = request.data.get('name')
        email = request.data.get('email')
        message = request.data.get('message')

        if not name or not email or not message:
            return Response({'error': 'All fields are required.'}, status=status.HTTP_400_BAD_REQUEST)

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
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            username = serializer.validated_data['username']

            if User.objects.filter(email=email).exists():
                return Response({'error': 'Email is already registered'}, status=status.HTTP_400_BAD_REQUEST)
            if User.objects.filter(username=username).exists():
                return Response({'error': 'Username is already taken'}, status=status.HTTP_400_BAD_REQUEST)

            serializer.save()
            return Response({'message': 'User registered successfully'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Login API (by email and password)
# class LoginAPI(APIView):
#     def post(self, request):
#         serializer = LoginSerializer(data=request.data)
#         if serializer.is_valid():
#             username = serializer.validated_data['username']
#             password = serializer.validated_data['password']

#             try:
#                 user = User.objects.get(username=username)
#             except User.DoesNotExist:
#                 return Response({'error': 'Invalid username or password'}, status=status.HTTP_401_UNAUTHORIZED)

#             user = authenticate(username=user.username, password=password)
#             if user:
#                 return Response({'message': 'Login successful',}, status=status.HTTP_200_OK)

#             return Response({'error': 'Invalid username or password'}, status=status.HTTP_401_UNAUTHORIZED)

#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginAPI(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']

            user = authenticate(username=user.username, password=password)

            if user is not None:
                # ✅ Create or get the user's token
                token, created = Token.objects.get_or_create(user=user)
                return Response({
                    'message': 'Login successful',
                    'token': token.key
                }, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Invalid username or password'}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    

@method_decorator(csrf_exempt, name='dispatch')
class InterviewBotAPI(APIView):
    def post(self, request):
        user_input = request.data.get('input')
        if not user_input:
            return Response({'error': 'Input is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        ngrok_url = "https://e6b4-35-199-148-56.ngrok-free.app/"  # Your bot endpoint
        
        try:
            # Forward user input to ngrok bot
            ngrok_response = requests.post(ngrok_url, json={'input': user_input}, timeout=10)
            ngrok_response.raise_for_status()
            
            # Parse response from bot
            bot_reply = ngrok_response.json()
            
            # Return bot's response to user
            return Response({'response': bot_reply}, status=status.HTTP_200_OK)
        
        except requests.RequestException as e:
            return Response({'error': 'Failed to connect to interview bot.', 'details': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        
# class ChatbotAPI(APIView):
#     def post(self, request):
#         serializer = ChatbotQuerySerializer(data=request.data)
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         query = serializer.validated_data['query']
#         chatbot_type = serializer.validated_data['chatbot_type']
        
#         try:
#             if chatbot_type == 'indeed':
#                 response = get_indeed_response(query)
#             else:
#                 response = get_gmtt_response(query)
#             return Response({
#                 'response': response,
#                 'chatbot': chatbot_type
#             }, status=status.HTTP_200_OK)
            
#         except Exception as e:
#             logging.error(f"Chatbot error: {str(e)}")
#             return Response({
#                 'error': 'An error occurred while processing your request',
#                 'details': str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# from .models import ChatbotConversation
# from .serializers import ChatbotConversationSerializer

class ChatbotAPI(APIView):
    def post(self, request):
        serializer = ChatbotQuerySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        query = serializer.validated_data['query']
        chatbot_type = serializer.validated_data['chatbot_type']
        user = request.user

        try:
            if chatbot_type == 'indeed':
                response = get_indeed_response(query)
            else:
                response = get_gmtt_response(query)

            # Save conversation
            ChatbotConversation.objects.create(
                user=user,
                chatbot_type=chatbot_type,
                query=query,
                response=response
            )

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