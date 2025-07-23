import boto3
import os
import uuid
from django.conf import settings
from urllib.parse import urljoin

class AWSPollyService:
    def __init__(self):
        self.client = boto3.client(
            'polly',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        self.voice_mapping = {
            'en': 'Kajal',      # English (Indian accent)
            'hi': 'Aditi',      # Hindi
            'mr': 'Aditi',      # Marathi
        }

    def synthesize_speech(self, text, language_code='en', save_to_file=False):
        try:
            voice_id = self.voice_mapping.get(language_code, 'Kajal')
            
            response = self.client.synthesize_speech(
                Text=text,
                OutputFormat='mp3',
                VoiceId=voice_id,
                Engine='neural'
            )
            
            audio_stream = response['AudioStream'].read()
            
            if save_to_file:
                # Generate unique filename
                filename = f"speech_{uuid.uuid4()}.mp3"
                filepath = os.path.join(settings.MEDIA_ROOT, 'polly_audio', filename)
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                # Save the audio file
                with open(filepath, 'wb') as f:
                    f.write(audio_stream)
                
                # Generate URL for the audio file
                audio_url = urljoin(settings.MEDIA_URL, f'polly_audio/{filename}')
            else:
                audio_url = None
            
            return {
                'text': text,
                'audio_url': audio_url,
                'audio_stream': audio_stream if not save_to_file else None,
                'success': True
            }
            
        except Exception as e:
            return {
                'text': text,
                'error': str(e),
                'success': False
            }