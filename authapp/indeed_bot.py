from .common_utils import *
from urllib.parse import urljoin
from .website_scraper import build_website_guide
from .website_guide import get_website_guide_response
import os
import json
import requests
import uuid
from django.contrib.auth import get_user_model
from .models import ChatbotConversation
from .serializers import ChatbotConversationSerializer
import random

User = get_user_model()

MISTRAL_API_KEY = "5jMPffjLAwLyyuj6ZwFHhbLZxb2TyfUR"

CHATBOT_NAME = "Infi"

# Build absolute paths to JSON files
current_dir = os.path.dirname(__file__)
json_dir = os.path.join(current_dir, "json_files")

greetings_path = os.path.join(json_dir, "greetings.json")
farewells_path = os.path.join(json_dir, "farewells.json")
general_path = os.path.join(json_dir, "general.json")
content_path = os.path.join(json_dir, "content.json")
history_file_path = os.path.join(json_dir, "session_history_iipt.json")

# Ensure history file exists
if not os.path.exists(history_file_path):
    with open(history_file_path, "w") as f:
        json.dump([], f)

# Load knowledge bases
greetings_kb = load_json_data(greetings_path).get("greetings", {})
farewells_kb = load_json_data(farewells_path).get("farewells", {})
general_kb = load_json_data(general_path).get("general", {})
indeed_kb = load_knowledge_base(content_path)

# Language mapping for translation
LANGUAGE_MAPPING = {
    'mr': 'marathi',
    'hi': 'hindi',
    'en': 'english'
}


def handle_meta_questions(user_input):
    """
    Handle meta-questions like 'what can I ask you' or 'how can you help me?'
    Returns a general assistant response if a match is found.
    """
    meta_phrases = [
        "what can i ask you", "suggest me some topics", "what topics can i ask", 
        "how can you help", "what do you know", "what services do you provide",
        "what questions can i ask"
    ]
    lowered = user_input.lower()
    if any(phrase in lowered for phrase in meta_phrases):
        responses = [
            "I'm here to assist you with anything related to Indeed Inspiring Infotech. Ask away!",
            "You can ask me about our work, services, training, or anything else about the company.",
            "Happy to help with queries about Indeed Inspiring Infotech — what would you like to know?",
            "Feel free to explore topics like our expertise, projects, or team. How can I assist?"
        ]
        return random.choice(responses)
    return None


def store_session_in_db(history, user, chatbot_type):
    session_id = str(uuid.uuid4())
    print(f"\n[DB] Saving session with ID: {session_id}")
    print(f"[DB] User: {user}, Type: {chatbot_type}, History Length: {len(history)}")

    for i, turn in enumerate(history):
        print(f"[DB] Inserting Turn {i+1}: User = {turn['user']}, Bot = {turn['bot']}")
        ChatbotConversation.objects.create(
            user=user,
            chatbot_type=chatbot_type,
            session_id=session_id,
            query=turn["user"],
            response=turn["bot"]
        )

    print(f"[DB] Session {session_id} successfully stored.\n")
    return session_id

# Crawl website initially
def crawl_indeed_website():
    global INDEED_INDEX
    INDEED_INDEX = crawl_website("https://indeedinspiring.com/", max_pages=30)
    print(f"[INFO] Crawled {len(INDEED_INDEX)} pages from indeedinspiring.com")
    return INDEED_INDEX

INDEED_INDEX = crawl_indeed_website()

def detect_input_language_type(text):
    """Detect if input is in English script or native script"""
    # If more than 70% characters are ASCII, consider it English script
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return 'english_script' if (ascii_chars / len(text)) > 0.7 else 'native_script'

def detect_language(text):
    try:
        detected = detect(text)
        return detected if detected in LANGUAGE_MAPPING else 'en'
    except LangDetectException as e:
        print(f"[ERROR] Language detection failed: {e}")
        return 'en'

def translate_to_english(text):
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except Exception as e:
        print(f"[ERROR] Translation to English failed: {e}")
        return text

def translate_response(response_text, target_lang, input_script_type):
    """Translate response based on input language and script type"""
    try:
        if target_lang == 'en':
            return response_text
        
        # First translate to target language
        translated = GoogleTranslator(source='en', target=target_lang).translate(response_text)
        
        # If input was in English script (like "namaskar" for Marathi), transliterate
        if input_script_type == 'english_script' and target_lang in ['hi', 'mr', 'ta', 'te', 'kn', 'gu', 'bn', 'pa']:
            try:
                # Convert to native script first
                native_script = translated
                # Then transliterate back to English script
                english_script = transliterate(native_script, sanscript.DEVANAGARI, sanscript.ITRANS)
                return english_script
            except Exception as e:
                print(f"[ERROR] Transliteration failed: {e}")
                return translated
        return translated
    except Exception as e:
        print(f"[ERROR] Response translation failed: {e}")
        return response_text

import re

def split_into_individual_questions(text):
    # Split using question marks, periods, or connectors like 'and', 'also'
    parts = re.split(r'[?।]|(?<!\w)(?:and|also|&)(?!\w)', text, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


def call_mistral_model(prompt, max_tokens=200):
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-small",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content'].strip()
    else:
        print(f"[ERROR] Mistral API failed: {response.status_code} {response.text}")
        return "I'm having trouble accessing information right now. Please try again later."


def get_mistral_indeed_response(user_query):
    try:
        match = find_matching_content(user_query, INDEED_INDEX, threshold=0.6)

        best_match = None
        best_score = 0
        query_keywords = set(user_query.lower().split())

        for url, data in INDEED_INDEX.items():
            page_keywords = set(data['text'].lower().split())
            match_score = len(query_keywords & page_keywords)
            if match_score > best_score:
                best_match = data
                best_score = match_score

        context = """
        Indeed Inspiring Infotech is a technology company providing innovative IT solutions.
        Key Information:
        - Founded by Kushal Sharma in 2016
        - Specializes in AI, web development, and digital transformation
        - Website: https://indeedinspiring.com
        """

        if match:
            context += f"\n\nRelevant page content from {match['title']}:\n{match['text']}"
            print(f"[DEBUG] Matched page title: {match['title']}")
            print(f"[DEBUG] Matched page snippet:\n{match['text'][:500]}")

        prompt = f"""You are an assistant for Indeed Inspiring Infotech and developed by Indeed Inspiring AIML team.

Strict Rules:
1. Only provide information about Indeed Inspiring Infotech from the website indeedinspiring.com
2. Also handle general greetings and farewells and general conversations like hi, hello, how are you, etc.
3. For unrelated topics, reply that you don’t have info on that and focus only on Indeed Inspiring Infotech. Include the topic name in your response. Rephrase each time.
4. Keep responses concise (1 sentence maximum)
5. If needed, mention to visit indeedinspiring.com for more details

Context: {context}

User Query: {user_query}

Response:"""

        return call_mistral_model(prompt)

    except Exception as e:
        print(f"[ERROR] Mistral call failed: {e}")
        return "I'm having trouble accessing company information right now. Please visit indeedinspiring.com for details."


def update_and_respond_with_history(user_input, current_response, user=None, chatbot_type='indeed'):
    exit_keywords = ["bye", "bye bye", "exit"]
    history = load_session_history(history_file_path)

    print(f"[HISTORY] Loaded {len(history)} items from JSON file.")

    if any(kw in user_input.lower() for kw in exit_keywords):
        print("[HISTORY] Exit keyword detected. Attempting to save session to DB...")
        
        store_session_in_db(history, user, chatbot_type)
        print("[HISTORY] Session saved to DB. Clearing history file.")
        open(history_file_path, "w").close()
        print("[HISTORY] Cleared session history JSON file.")
        return current_response

    # Load full history but use only the last 3 turns for context
    recent_history = history[-3:]

    history_text = ""
    for turn in recent_history:
        history_text += f"User: {turn['user']}\nBot: {turn['bot']}\n"
 
    prompt = f"""
        You are a smart assistant representing Indeed Inspiring Infotech.
        Use the conversation history ,current user query below and the current system reply to generate a final response.
        Rules:
        1. Keep your responses concise and limited to 1 sentence.
        2. Only use phrases like "As I mentioned earlier," if the user has asked a similar or rephrased question earlier in this session.
        3. Do NOT use such phrases if this is the user's first time asking about the topic.
        4. Use past context only if the new question matches a previous one in meaning; otherwise, treat it independently.
        Conversation History:
        {history_text}
        Current User Query:
        {user_input}
        Current System Response:
        {current_response}
        Final Answer:
        """

    try:
        final_response = call_mistral_model(prompt, max_tokens=250)
        history.append({"user": user_input, "bot": final_response})
        save_session_history(history_file_path, history)
        return final_response
    except Exception as e:
        print(f"[ERROR] History response generation failed: {e}")
        history.append({"user": user_input, "bot": current_response})
        save_session_history(history_file_path, history)
        return current_response

# def get_indeed_response(user_input, user=None):
#     if not user_input or not isinstance(user_input, str) or len(user_input.strip()) == 0:
#         return "Please provide a valid input."

#     # Step 1: Detect input language and script type
#     input_lang = detect_language(user_input)
#     script_type = detect_input_language_type(user_input)
#     print(f"[DEBUG] Input language detected: {input_lang}, Script type: {script_type}")

#     # Step 2: Translate input to English if needed
#     translated_input = translate_to_english(user_input) if input_lang != "en" else user_input
#     if input_lang != "en":
#         print(f"[DEBUG] Translated input to English: {translated_input}")
    
#     meta_response = handle_meta_questions(translated_input)
#     # Step 3: Chatbot processing
#     response = None

#     if not response and ("what is your name" in translated_input.lower() or "your name" in translated_input.lower()):
#         print("[INFO] Response from: Name handler")
#         response = f"My name is {CHATBOT_NAME}. How can I assist you with Indeed Inspiring Infotech?"
#         return update_and_respond_with_history(user_input, response, user=user, chatbot_type='indeed')
    
        
#     if meta_response:
#         print("[INFO] Response from: Meta Question Handler")
#         return update_and_respond_with_history(user_input, meta_response, user=user, chatbot_type='indeed')



#     if response := search_knowledge(user_input, indeed_kb):
#         print("[INFO] Response from: Knowledge Base")
#         return update_and_respond_with_history(user_input, response, user=user, chatbot_type='indeed')

#     if response := handle_time_based_greeting(user_input):
#         print("[INFO] Response from: Time-Based Greeting")
#         return update_and_respond_with_history(user_input, response, user=user, chatbot_type='indeed')

#     if response := handle_date_related_queries(user_input):
#         print("[INFO] Response from: Date Handler")
#         return update_and_respond_with_history(user_input, response, user=user, chatbot_type='indeed')

#     if response := generate_nlp_response(user_input):
#         print("[INFO] Response from: NLP Generator")
#         return update_and_respond_with_history(user_input, response, user=user, chatbot_type='indeed')

#     print("[INFO] Response from: Mistral API")
#     response = get_mistral_indeed_response(user_input)
#     return update_and_respond_with_history(user_input, response, user=user, chatbot_type='indeed')

def get_indeed_response(user_input, user=None):
    if not user_input or not isinstance(user_input, str) or len(user_input.strip()) == 0:
        return "Please provide a valid input."

    input_lang = detect_language(user_input)
    script_type = detect_input_language_type(user_input)
    translated_input = translate_to_english(user_input) if input_lang != "en" else user_input
    questions = split_into_individual_questions(translated_input)

    final_responses = []

    for question in questions:
        question = question.strip()
        if not question:
            continue

        # 1. Meta questions
        meta_response = handle_meta_questions(question)
        if meta_response:
            final_responses.append(meta_response)
            continue

        # 2. Name handler
        if "your name" in question.lower():
            final_responses.append(f"My name is {CHATBOT_NAME}. How can I assist you with Indeed Inspiring Infotech?")
            continue

        # 3. Knowledge Base
        kb_response = search_knowledge(question, indeed_kb)
        if kb_response:
            final_responses.append(kb_response)
            continue

        # 4. Greeting
        greeting_response = handle_time_based_greeting(question)
        if greeting_response:
            final_responses.append(greeting_response)
            continue

        # 5. Date/Time
        date_response = handle_date_related_queries(question)
        if date_response:
            final_responses.append(date_response)
            continue

        # 6. NLP or fallback to Mistral
        response = generate_nlp_response(question) or get_mistral_indeed_response(question)
        final_responses.append(response)

    # Merge responses into a brief final message
    final_output = " ".join(final_responses)
    return update_and_respond_with_history(user_input, final_output, user=user, chatbot_type='indeed')
