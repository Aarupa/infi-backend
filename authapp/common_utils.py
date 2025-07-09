import os
import json
import re
import random
import logging
from datetime import datetime, timedelta
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import spacy
from deep_translator import GoogleTranslator
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
from deep_translator import GoogleTranslator

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
    try:
        logging.info(f"Saving session history to {file_path}: {history[-5:]}")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history[-5:], f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save session history: {e}")

LANGUAGE_MAPPING = {
    'mr': 'marathi',
    'hi': 'hindi',
    'en': 'english'
}



    
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
def generate_nlp_response(msg, bot_name="Suraksha Mitra"):
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
SUPPORTED_LANGUAGES = ['en', 'hi', 'mr']

# In common_utils.py, add near generate_nlp_response()
def handle_off_topic(query, current_lang):
    """More graceful handling of non-safety questions"""
    responses = {
        'hi': (
            "मैं केवल कार्यस्थल सुरक्षा से संबंधित प्रश्नों में मदद कर सकता हूँ। "
            "क्या आप कार्यस्थल सुरक्षा के बारे में कोई प्रश्न पूछना चाहेंगे?"
        ),
        'mr': (
            "मी फक्त कामाच्या ठिकाणच्या सुरक्षिततेशी संबंधित प्रश्नांमध्ये मदत करू शकतो. "
            "तुम्हाला कामाच्या ठिकाणच्या सुरक्षिततेबद्दल काही प्रश्न विचारायचे आहेत का?"
        ),
        'en': (
            "I can only assist with workplace safety-related questions. "
            "Would you like to ask something about workplace safety?"
        )
    }
    
    # Include a safety tip in the same language
    safety_tips = {
        'hi': "सुरक्षा सुझाव: हमेशा अपने कार्यक्षेत्र में संभावित खतरों के प्रति सजग रहें।",
        'mr': "सुरक्षा टीप: नेहमी तुमच्या कामाच्या क्षेत्रातील संभाव्य धोक्यांवर लक्ष ठेवा.",
        'en': "Safety tip: Always be aware of potential hazards in your work area."
    }
    
    return f"{responses.get(current_lang, responses['en'])} {safety_tips.get(current_lang, safety_tips['en'])}"

def detect_language(text):
    try:
        lang = detect(text)
        return lang if lang in LANGUAGE_MAPPING else 'en'
    except LangDetectException as e:
        print(f"[ERROR] Language detection failed: {e}")
        return 'en'
def detect_input_language_type(text):
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return 'english_script' if (ascii_chars / len(text)) > 0.7 else 'native_script'

def detect_language_variant(text):
    try:
        # First check for obvious mixed language patterns
        text_lower = text.lower()
        
        # Hinglish patterns (Hindi + English)
        if (any(word in text_lower for word in ['ky', 'kya', 'hote', 'hai', 'kaise']) and 
            any(word in text_lower for word in ['what', 'why', 'how', 'ppe', 'safety'])):
            return 'hinglish'
            
        # Minglish patterns (Marathi + English)
        if (any(word in text_lower for word in ['kay', 'ahe', 'ka', 'hot', 'ase']) and 
            any(word in text_lower for word in ['what', 'why', 'how', 'ppe', 'safety'])):
            return 'minglish'
        
        # Pure language detection
        lang_code = detect(text)
        
        # For short texts, rely more on character analysis
        if len(text) < 10:
            devanagari_chars = sum(1 for c in text if '\u0900' <= c <= '\u097F')
            if devanagari_chars / len(text) > 0.5:
                return 'hi' if lang_code == 'hi' else 'mr'
        
        if lang_code == 'hi':
            return 'hi'
        elif lang_code == 'mr':
            return 'mr'
        else:
            return 'en'
            
    except LangDetectException:
        # Fallback to character analysis
        devanagari_chars = sum(1 for c in text if '\u0900' <= c <= '\u097F')
        if devanagari_chars / len(text) > 0.7:
            return 'hi'  # Default to Hindi if mostly Devanagari
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
        "Would you like to know about essential safety gear for working at heights?",
        "I can guide you through the common hazards associated with height work. Interested?",
        "Shall I share key safety protocols for working at elevated locations?"
    ],
    'mid': [
        "What would you like to focus on — PPE, fall protection systems, or training requirements?",
        "Do you want details on safe practices for ladders, scaffolding, or harness usage?",
        "I can also provide tips on how to inspect safety gear before height work, if you'd like?"
    ],
    'closing': [
        "Before we finish, is there anything else you'd like to know about height safety?",
        "Would you like a checklist or guideline document for working at heights?",
        "Shall I connect you with our safety officer for more personalized advice?"
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

# In common_utils.py, add after CONVERSATION_PROMPTS
def get_localized_driver(history, stage, language):
    """Return conversation drivers in the same language as the conversation"""
    drivers = {
        'hi': {
            'intro': [
                "क्या आप ऊंचाई पर काम करने के लिए आवश्यक सुरक्षा उपकरणों के बारे में जानना चाहेंगे?",
                "मैं आपको ऊंचाई पर काम से जुड़े सामान्य खतरों के बारे में मार्गदर्शन कर सकता हूं। क्या आप रुचि रखते हैं?"
            ],
            'mid': [
                "आप किस पर ध्यान देना चाहेंगे - पीपीई, फॉल प्रोटेक्शन सिस्टम, या प्रशिक्षण आवश्यकताएं?",
                "क्या आप सीढ़ी, मचान या हार्नेस उपयोग के लिए सुरक्षित प्रथाओं के बारे में विवरण चाहते हैं?"
            ]
        },
        'mr': {
            'intro': [
                "तुम्हाला उंचावर काम करण्यासाठी आवश्यक सुरक्षा उपकरणांबद्दल जाणून घ्यायचे आहे का?",
                "मी तुम्हाला उंचावरच्या कामाशी संबंधित सामान्य धोक्यांबद्दल मार्गदर्शन करू शकतो. तुम्हाला रस आहे का?"
            ],
            'mid': [
                "तुम्ही कशावर लक्ष केंद्रित करू इच्छिता - पीपीई, फॉल प्रोटेक्शन सिस्टम किंवा प्रशिक्षण आवश्यकता?",
                "तुम्हाला शिडी, स्कॅफोल्डिंग किंवा हार्नेस वापरासाठी सुरक्षित पद्धतींबद्दल तपशील हवे आहेत का?"
            ]
        }
    }
    
    if language in drivers:
        return random.choice(drivers[language].get(stage, [""]))
    return random.choice(CONVERSATION_PROMPTS.get(stage, [""]))

# In common_utils.py, add after translate_response() function
def improve_transliteration(text, target_lang):
    """Clean up common transliteration artifacts"""
    common_fixes = {
        'hi': [
            ('UMchAI', 'Unchai'),
            ('kAma', 'kaam'),
            ('surakShA', 'suraksha'),
            ('shUza', 'shoes')
        ],
        'mr': [
            ('pIpII', 'PPE'),
            ('nirIkShaNa', 'nirikshan')
        ]
    }
    
    for lang, fixes in common_fixes.items():
        if target_lang == lang:
            for wrong, right in fixes:
                text = text.replace(wrong, right)
    return text