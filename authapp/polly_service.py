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
    def synthesize_speech_stream(self, text, language_code='en'):
        try:
            voice_id = self.voice_mapping.get(language_code, 'Kajal')

            response = self.client.synthesize_speech(
                Text=text,
                OutputFormat='mp3',
                VoiceId=voice_id,
                Engine='neural'
            )

            # return the stream object (not read it!)
            return {
                'stream': response['AudioStream'],
                'success': True
            }

        except Exception as e:
            return {
                'error': str(e),
                'success': False
            }
