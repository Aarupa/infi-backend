import os
import json
import re
import random
import logging
from datetime import datetime, timedelta
from fuzzywuzzy import fuzz
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import spacy
from deep_translator import GoogleTranslator
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

# Initialize NLP and sentiment analysis
nlp = spacy.load("en_core_web_sm")
# nltk.download('wordnet')
sentiment_analyzer = SentimentIntensityAnalyzer()

# -------------------- JSON Loader --------------------
def load_json_data(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading {file_path}: {e}")
        return {}

def load_session_history(file_path):
    if os.path.exists(file_path):
        try:
            return load_json_data(file_path) or []
        except Exception:
            return []
    return []

def save_session_history(file_path, history):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(history[-5:], f, indent=2)





    
# -------------------- Knowledge Base Loader --------------------
def load_knowledge_base(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Get the list of intents
            intents = data.get('faqs', {}).get('intents', [])
            knowledge_base = []
            for item in intents:
                entry = {
                    'tag': item.get('tag'),
                    'patterns': [k.lower() for k in item.get('patterns', [])],
                    'responses': item.get('responses', []),
                    'follow_up': item.get('follow_up', ''),
                    'next_suggestions': item.get('next_suggestions', []),
                    'related_image_link': item.get('related_image_link', '')
                }
                knowledge_base.append(entry)
            return knowledge_base
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading {file_path}: {e}")
        return []


# -------------------- Time & Date Utilities --------------------
def handle_time_based_greeting(msg):
    greetings = ["good morning", "good afternoon", "good evening", "good night"]
    msg_lower = msg.lower()
    current_hour = datetime.now().hour

    for greeting in greetings:
        if greeting in msg_lower:
            if greeting == "good morning":
                return "Good morning! How can I assist you today?" if current_hour < 12 else "It's already past morning, but good day to you!"
            elif greeting == "good afternoon":
                return "Good afternoon! How can I assist you today?" if 12 <= current_hour < 18 else "It's not quite afternoon, but good day to you!"
            elif greeting == "good evening":
                return "Good evening! How can I assist you today?" if current_hour >= 18 else "It's not evening yet, but good day to you!"
            elif greeting == "good night":
                return "Good night! Sleep well and take care!"

    if "current time" in msg_lower:
        return f"The current time is {datetime.now().strftime('%H:%M:%S')}."
    return None

def handle_date_related_queries(msg):
    msg_lower = msg.lower()
    today = datetime.now()

    date_mapping = {
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "day after tomorrow": today + timedelta(days=2),
        "yesterday": today - timedelta(days=1),
        "day before yesterday": today - timedelta(days=2),
        "next week": today + timedelta(weeks=1),
        "last week": today - timedelta(weeks=1),
        "next month": (today.replace(day=28) + timedelta(days=4)).replace(day=1),
        "last month": (today.replace(day=1) - timedelta(days=1)).replace(day=1),
        "next year": today.replace(year=today.year + 1),
        "last year": today.replace(year=today.year - 1)
    }

    for key, date in date_mapping.items():
        if key in msg_lower:
            if "date" in msg_lower:
                return f"The {key}'s date is {date.strftime('%B %d, %Y')}."
            elif "day" in msg_lower:
                return f"The {key} is {date.strftime('%A')}."

    return None




# -------------------- Basic NLP Smalltalk --------------------
def generate_nlp_response(msg, bot_name="infi"):
    doc = nlp(msg)
    greetings = ["hi", "hello", "hey", "hii"]

    if any(token.lower_ in greetings for token in doc):
        return random.choice([f"Hello! I'm {bot_name}. How can I help you today?"])
    elif "how are you" in msg.lower():
        return random.choice(["I'm doing great, thanks for asking!", "I'm good! How about you?"])
    elif msg.lower() in ["great", "good", "awesome"]:
        return random.choice(["Glad to hear that!", "That's wonderful!"])
    elif "thank you" in msg.lower() or "thanks" in msg.lower():
        return random.choice(["You're welcome!", "Happy to help!"])
    elif "bye" in msg.lower() or "exit" in msg.lower():
        return "Goodbye! Have a great day!"

    return None


DEFAULT_LANG = "en"
SUPPORTED_LANGUAGES = ['en', 'hi', 'mr', 'ta', 'te', 'kn', 'gu', 'bn', 'pa', 'fr', 'de', 'es', 'ja', 'ko', 'zh']

def detect_language(text):
    try:
        lang = detect(text)
        return lang if lang in LANGUAGE_MAPPING else 'en'
    except LangDetectException as e:
        print(f"[ERROR] Language detection failed: {e}")
        return 'en'


def translate_to_english(text):
    if not text or len(text.strip()) < 2:
        return text
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except Exception as e:
        print(f"[ERROR] Translation to English failed: {e}")
        return text


# Conversation driving prompts
CONVERSATION_PROMPTS = {
    'intro': [
        "Would you like to know about our current plantation projects?",
        "I can tell you about our volunteer opportunities if you're interested?",
        "Shall I share some success stories from our recent initiatives?"
    ],
    'mid': [
        "What aspect interests you most - our methodology, impact, or how to get involved?",
        "Would you like details about any specific region we work in?",
        "I could also share some interesting facts about Peepal trees if you'd like?"
    ],
    'closing': [
        "Before we wrap up, is there anything else you'd like to know?",
        "Would you like me to send you more information via email?",
        "Shall I connect you with our volunteer coordinator?"
    ]
}

def get_conversation_driver(history, stage):
    """Generate context-aware conversation drivers"""
    if len(history) < 2:
        return random.choice(CONVERSATION_PROMPTS['intro'])
    
    last_question = history[-1]["user"].lower()
    
    if any(kw in last_question for kw in ["thank", "bye", "enough"]):
        return random.choice(CONVERSATION_PROMPTS['closing'])
    
    if len(history) > 4:
        return random.choice(CONVERSATION_PROMPTS['mid'])
    
    # Default follow-up based on context
    context_keywords = ["plant", "tree", "volunteer", "donat", "project"]
    for kw in context_keywords:
        if kw in last_question:
            return f"Would you like more details about our {kw} programs?"
    
    return random.choice(CONVERSATION_PROMPTS['mid'])

INDEED_CONVERSATION_PROMPTS = {
    'intro': [
        "Would you like to know about our IT services and solutions?",
        "I can tell you about our technology expertise if you're interested?",
        "Shall I share some of our recent client success stories?"
    ],
    'mid': [
        "What interests you most - our AI solutions, web development, or digital transformation services?",
        "Would you like details about any specific technology we specialize in?",
        "I could also share information about our team's expertise if you'd like?"
    ],
    'closing': [
        "Before we finish, is there anything else about Indeed Inspiring Infotech you'd like to know?",
        "Would you like me to connect you with our solutions team?",
        "Should I email you more information about our services?"
    ],
    'tech_focus': [
        "Would you like more details about our {0} implementations?",
        "I can share some case studies of our {0} projects if you're interested?",
        "Our {0} expertise is particularly strong - would you like to know more?"
    ]
}

def get_indeed_conversation_driver(history, stage):
    """Generate context-aware conversation drivers for Indeed Inspiring Infotech"""
    if len(history) < 2:
        return random.choice(INDEED_CONVERSATION_PROMPTS['intro'])
    
    last_question = history[-1]["user"].lower()
    
    if any(kw in last_question for kw in ["thank", "bye", "enough"]):
        return random.choice(INDEED_CONVERSATION_PROMPTS['closing'])
    
    if len(history) > 4:
        return random.choice(INDEED_CONVERSATION_PROMPTS['mid'])
    
    # Tech-focused follow-ups
    tech_keywords = {
        'ai': ['ai', 'artificial intelligence', 'machine learning', 'ml'],
        'web': ['web', 'website', 'frontend', 'backend'],
        'digital': ['digital', 'transformation', 'dx'],
        'cloud': ['cloud', 'aws', 'azure', 'gcp']
    }
    
    for tech, keywords in tech_keywords.items():
        if any(kw in last_question for kw in keywords):
            return random.choice(INDEED_CONVERSATION_PROMPTS['tech_focus']).format(tech)
    
    # Business-focused follow-ups
    business_keywords = ['service', 'solution', 'product', 'offer']
    if any(kw in last_question for kw in business_keywords):
        return "Would you like to know more about how we tailor solutions for specific industries?"
    
    return random.choice(INDEED_CONVERSATION_PROMPTS['mid'])

# -------------------- Miscellaneous Utilities --------------------
# Add to common_utils.py
CONTACT_EMAIL = "iipt.aiml@gmail.com"

def is_contact_request(text):
    """Check if user wants to connect/contact"""
    contact_keywords = [
        'contact', 'connect', 'reach out', 'talk to someone',
        'email', 'phone', 'number', 'speak with'
    ]
    return any(keyword in text.lower() for keyword in contact_keywords)

def is_info_request(text):
    """Check if user is providing information"""
    info_keywords = [
        'my name is', 'i am', 'email is', 'contact is',
        'you can reach me at', 'my number is'
    ]
    return any(keyword in text.lower() for keyword in info_keywords)