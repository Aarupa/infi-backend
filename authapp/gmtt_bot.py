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

User = get_user_model()

MISTRAL_API_KEY = "5jMPffjLAwLyyuj6ZwFHhbLZxb2TyfUR"

CHATBOT_NAME = "Infi"

current_dir = os.path.dirname(__file__)
json_dir = os.path.join(current_dir, "json_files")

greetings_path = os.path.join(json_dir, "greetings.json")
farewells_path = os.path.join(json_dir, "farewells.json")
general_path = os.path.join(json_dir, "general.json")
content_path = os.path.join(json_dir, "trees.json")
history_file_path = os.path.join(json_dir, "session_history_gmtt.json")

if not os.path.exists(history_file_path):
    with open(history_file_path, "w") as f:
        json.dump([], f)

greetings_kb = load_json_data(greetings_path).get("greetings", {})
farewells_kb = load_json_data(farewells_path).get("farewells", {})
general_kb = load_json_data(general_path).get("general", {})
gmtt_kb = load_knowledge_base(content_path)

LANGUAGE_MAPPING = {
    'mr': 'marathi',
    'hi': 'hindi',
    'en': 'english'
}

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

def crawl_gmtt_website():
    print("[DEBUG] crawl_gmtt_website() called")
    global GMTT_INDEX
    GMTT_INDEX = crawl_website("https://www.givemetrees.org", max_pages=30)
    print(f"[INFO] Crawled {len(GMTT_INDEX)} pages from givemetrees.org")
    return GMTT_INDEX

GMTT_INDEX = crawl_gmtt_website()

def detect_input_language_type(text):
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
    try:
        if target_lang == 'en':
            return response_text
        translated = GoogleTranslator(source='en', target=target_lang).translate(response_text)
        if input_script_type == 'english_script' and target_lang in ['hi', 'mr', 'ta', 'te', 'kn', 'gu', 'bn', 'pa']:
            try:
                native_script = translated
                english_script = transliterate(native_script, sanscript.DEVANAGARI, sanscript.ITRANS)
                return english_script
            except Exception as e:
                print(f"[ERROR] Transliteration failed: {e}")
                return translated
        return translated
    except Exception as e:
        print(f"[ERROR] Response translation failed: {e}")
        return response_text

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

def get_mistral_gmtt_response(user_query):
    try:
        match = find_matching_content(user_query, GMTT_INDEX, threshold=0.6)

        best_match = None
        best_score = 0
        query_keywords = set(user_query.lower().split())

        for url, data in GMTT_INDEX.items():
            page_keywords = set(data['text'].lower().split())
            match_score = len(query_keywords & page_keywords)
            if match_score > best_score:
                best_match = data
                best_score = match_score

        context = """
        Give Me Trees Foundation is a non-profit organization founded in 1978 by Swami Prem Parivartan (Peepal Baba).
        It focuses on environmental conservation through tree plantation, especially Peepal trees, across India.
        Website: https://www.givemetrees.org
        """

        if match:
            context += f"\n\nRelevant page content from {match['title']}:\n{match['text']}"
            print(f"[DEBUG] Matched page title: {match['title']}")
            print(f"[DEBUG] Matched page snippet:\n{match['text'][:500]}")

        prompt = f"""You are an assistant for Give Me Trees Foundation and developed by Give Me Trees AIML team.

Strict Rules:
1. Only provide information about Give Me Trees Foundation from the website givemetrees.org
2. Also handle general greetings and farewells and general conversations like hi, hello, how are you, etc.
3. For unrelated topics, reply that you don’t have info on that and focus only on Give Me Trees Foundation. Include the topic name in your response. Rephrase each time.
4. Keep responses concise (1 sentence maximum)
5. If needed, mention to visit givemetrees.org for more details

Context: {context}

User Query: {user_query}

Response:"""

        return call_mistral_model(prompt)

    except Exception as e:
        print(f"[ERROR] Mistral call failed: {e}")
        return "I'm having trouble accessing organization information right now. Please visit givemetrees.org for details."

def update_and_respond_with_history(user_input, current_response, user=None, chatbot_type='gmtt'):
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
    
    history_text = ""
    for turn in history[-5:]:
        history_text += f"User: {turn['user']}\nBot: {turn['bot']}\n"

    prompt = f"""
You are a smart assistant representing Give Me Trees Foundation.

Use the conversation history below and the current system reply to generate a final response.

Rules:
1. By default, keep your responses concise and limited to 1 sentence.
2. If the user has asked a similar or identical question earlier, start with something like \"As I mentioned earlier,\" and give a slightly expanded or rephrased version of the previous answer.
3. Keep responses concise (1 sentence maximum), but only if the topic has already been discussed before.
4. Keep responses natural, helpful, and non-repetitive.

Conversation History:
{history_text}

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

def get_gmtt_response(user_input, user=None):
    if not user_input or not isinstance(user_input, str) or len(user_input.strip()) == 0:
        return "Please provide a valid input."

    input_lang = detect_language(user_input)
    script_type = detect_input_language_type(user_input)
    print(f"[DEBUG] Input language detected: {input_lang}, Script type: {script_type}")

    translated_input = translate_to_english(user_input) if input_lang != "en" else user_input
    if input_lang != "en":
        print(f"[DEBUG] Translated input to English: {translated_input}")

    response = None

    if not response and ("what is your name" in translated_input.lower() or "your name" in translated_input.lower()):
        print("[INFO] Response from: Name handler")
        response = f"My name is {CHATBOT_NAME}. How can I assist you with Give Me Trees Foundation?"

    if response := search_knowledge(user_input, gmtt_kb):
        print("[INFO] Response from: Knowledge Base")
        return update_and_respond_with_history(user_input, response, user=user, chatbot_type='gmtt')

    if response := handle_time_based_greeting(user_input):
        print("[INFO] Response from: Time-Based Greeting")
        return update_and_respond_with_history(user_input, response, user=user, chatbot_type='gmtt')

    if response := handle_date_related_queries(user_input):
        print("[INFO] Response from: Date Handler")
        return update_and_respond_with_history(user_input, response, user=user, chatbot_type='gmtt')

    if response := generate_nlp_response(user_input):
        print("[INFO] Response from: NLP Generator")
        return update_and_respond_with_history(user_input, response, user=user, chatbot_type='gmtt')

    print("[INFO] Response from: Mistral API")
    response = get_mistral_gmtt_response(user_input)
    return update_and_respond_with_history(user_input, response, user=user, chatbot_type='gmtt')
