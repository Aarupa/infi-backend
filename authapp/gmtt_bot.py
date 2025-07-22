from .common_utils import *
import os
import json
import uuid
from django.contrib.auth import get_user_model
from .models import ChatbotConversation
import re
import requests
User = get_user_model()
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

MISTRAL_API_KEYS = [
    "5jMPffjLAwLyyuj6ZwFHhbLZxb2TyfUR",  # existing key
    "tZKRscT6hDUurE5B7ex5j657ZZQDQw3P",
    "3OyOnjAypy79EewldzfcBczW01mET0fM"
]

# Change the bot name here
CHATBOT_NAME = "Suraksha Mitra"
CURRENT_TOPIC = "Safety on height"  # Hardcoded topic for now

current_dir = os.path.dirname(__file__)
json_dir = os.path.join(current_dir, "json_files")

content_path = os.path.join(json_dir, "SafetyOnHeight.json")
history_file_path = os.path.join(json_dir, "session_history_gmtt.json")

if not os.path.exists(history_file_path):
    with open(history_file_path, "w") as f:
        json.dump([], f)

safety_kb = load_knowledge_base(content_path)

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

def detect_input_language_type(text):
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return 'english_script' if (ascii_chars / len(text)) > 0.7 else 'native_script'

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
        
        if input_script_type == 'english_script':
            try:
                return transliterate(translated, sanscript.DEVANAGARI, sanscript.ITRANS)
            except Exception as e:
                print(f"[ERROR] Transliteration failed: {e}")
                return translated
        else:
            return translated
    except Exception as e:
        print(f"[ERROR] Response translation failed: {e}")
        return response_text

def call_mistral_model(prompt, max_tokens=100):
    url = "https://api.mistral.ai/v1/chat/completions"
    
    for idx, api_key in enumerate(MISTRAL_API_KEYS):
        headers = {
            "Authorization": f"Bearer {api_key}",
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

        print(f"[MISTRAL API] Attempting with API key #{idx + 1}: {api_key[:5]}...")

        try:
            response = requests.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                print(f"[MISTRAL API] Success with API key #{idx + 1}")
                return response.json()['choices'][0]['message']['content'].strip()
            else:
                print(f"[MISTRAL API] Failed with key #{idx + 1}: {response.status_code} - {response.text}")

        except Exception as e:
            print(f"[MISTRAL API] Exception with key #{idx + 1}: {e}")

    # All keys failed
    print("[MISTRAL API] All API keys failed.")
    return "I'm having trouble accessing information right now. Please try again later."

def get_mistral_gmtt_response(user_query, history):
    try:
        prompt = f"""You assist with {CURRENT_TOPIC} safety only. Decline anything off-topic.

Context: {history[-2:] if history else 'New conversation'}
Query: {user_query}

Rules:
- 1 sentence reply
- Use real safety terms
- Never guess or repeat
- Occasionally end with a safety tip or question
- Unrelated? Respond: "Sorry, I can only help with {CURRENT_TOPIC} safety topics."

Answer:
"""
        response = call_mistral_model(prompt)
        cleaned_response = response.split('[/handling_instruction]')[-1]
        cleaned_response = cleaned_response.split('Response template:')[0]
        cleaned_response = re.sub(r'\[.*?\]', '', cleaned_response)
        cleaned_response = re.sub(r'(Answer:|Follow-up question:)', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = ' '.join(cleaned_response.split())
        if len(cleaned_response) > 0:
            cleaned_response = cleaned_response[0].upper() + cleaned_response[1:]
        return cleaned_response.strip()
    except Exception as e:
        driver = get_conversation_driver(history, 'mid')
        return f"I'd be happy to tell you more. {driver}"

def update_and_respond_with_history(user_input, current_response, user=None, chatbot_type='safety'):
    history = load_session_history(history_file_path)
    
    # Add conversation driver if missing
    if not any(punct in current_response[-1] for punct in ['?', '!']):
        driver = get_conversation_driver(history, 
                                      'intro' if len(history) < 2 else 'mid')
        current_response = f"{current_response} {driver}"
    
    # Ensure varied responses for repeated questions
    if any(h['user'].lower() == user_input.lower() for h in history[-3:]):
        current_response = f"Returning to your question, {current_response.lower()}"
    
    return current_response

def mistral_translate_response(response_text, target_lang_code):
    if target_lang_code == 'hinglish':
        prompt = f"""Translate the following English workplace safety instruction to clear and natural Hindi written in English letters (Hinglish).
Keep the translation short, meaningful, and easy to understand — like you're explaining to a common worker.
Avoid awkward mixing. Use common Hindi phrases and English technical terms like "fall protection", "harness", etc. Do NOT add any explanation.

Input:
{response_text}
"""
    else:
        return response_text  # No translation needed

    mistral_response = call_mistral_model(prompt, max_tokens=70).strip()
    if mistral_response.lower().startswith("hindi translation:"):
        mistral_response = mistral_response[len("Hindi Translation:"):].strip()

    match = re.search(r'"([^"]+)"', mistral_response)
    if match:
        cleaned = match.group(1).strip()
        if ':' in cleaned:
            cleaned = cleaned.split(':', 1)[1].strip()
    else:
        partial_match = re.search(r'"([^"]+)', mistral_response)
        if partial_match:
            cleaned = partial_match.group(1).strip()
            if ':' in cleaned:
                cleaned = cleaned.split(':', 1)[1].strip()
        else:
            cleaned = mistral_response.strip()

    last_dot_index = cleaned.rfind('.')
    if last_dot_index != -1:
        if last_dot_index > 0:
            char_before_dot = cleaned[last_dot_index - 1]
            if not char_before_dot.isdigit() or char_before_dot not in '12345':
                cleaned = cleaned[:last_dot_index + 1].strip()

    return cleaned

def get_mistral_safety_response(user_query, history):
    try:
        prompt = f"""You are a {CURRENT_TOPIC} safety assistant.

Your job:
1. Only answer {CURRENT_TOPIC} safety questions.
2. Decline all unrelated queries with: "Sorry, I can only help with {CURRENT_TOPIC} safety topics."
3. Use accurate, real-world safety terms.
4. Guide the conversation with tips or follow-up safety questions.
5. Stay concise, professional, and supportive.
6. Never invent or guess answers.

Context:
{history[-2:] if history else 'New conversation'}

Query: {user_query}

Respond in 1–2 sentences, end with a safety tip or question.
"""
        response = call_mistral_model(prompt)
        cleaned_response = response.split('[/handling_instruction]')[-1]
        cleaned_response = cleaned_response.split('Response template:')[0]
        cleaned_response = re.sub(r'\[.*?\]', '', cleaned_response)
        cleaned_response = re.sub(r'(Answer:|Follow-up question:)', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = ' '.join(cleaned_response.split())
        if len(cleaned_response) > 0:
            cleaned_response = cleaned_response[0].upper() + cleaned_response[1:]
        return cleaned_response.strip()
    except Exception as e:
        driver = get_conversation_driver(history, 'mid')
        return f"I'd be happy to tell you more. {driver}"

def search_intents_and_respond_safety(user_input, safety_kb):
    """
    Uses Mistral API to answer ONLY using content from content.json (safety_kb).
    Always take initiative to keep the conversation going and make it look natural.
    Always use 'we' instead of 'they' when referring to the organization or its services, and answer as if you are part of safety.
    """
    # Flatten all content from safety_kb into a single context string
    context = ""
    if isinstance(safety_kb, dict):
        for key, value in safety_kb.items():
            if isinstance(value, dict):
                for subkey, subval in value.items():
                    context += f"{subkey}: {subval}\n"
            else:
                context += f"{key}: {value}\n"
    elif isinstance(safety_kb, list):
        for item in safety_kb:
            context += f"{item}\n"
    else:
        context = str(safety_kb)

    prompt = f"""You are a {CURRENT_TOPIC} safety bot. Use only the info below to answer.

     If a question isn't about {CURRENT_TOPIC} or not covered, say:
     "Sorry, I can only assist with {CURRENT_TOPIC} safety questions based on the safety guidelines I have."

     Do not guess or share personal opinions. Keep replies short, practical, and end with a safety tip or follow-up.

     ---SAFETY INFO---
     {context}
     ---END---

     User: {user_input}
     Answer:
     """

    response = call_mistral_model(prompt, max_tokens=100)
    response = re.sub(r'\[.*?\]', '', response)
    return response.strip()

def get_safety_response(user_input, user=None):
    print(type(safety_kb))
    # Input validation
    if not user_input or not isinstance(user_input, str) or len(user_input.strip()) == 0:
        return "Please provide a valid input."

    # Load conversation history
    history = load_session_history(history_file_path)
    
    # --- Clear session if user says bye ---
    if user_input.strip().lower() in ["bye", "goodbye", "see you", "exit", "quit"]:
        with open(history_file_path, "w") as f:
            json.dump([], f)
        return "Goodbye! Your session has been cleared. Stay safe!"

    # Language detection and translation
    input_lang = detect_language_variant(user_input)
    script_type = 'english_script' if input_lang in ['hinglish', 'minglish'] else detect_input_language_type(user_input)

    translated_input = translate_to_english(user_input) if input_lang not in ['en', 'hinglish', 'minglish'] else user_input

    # Response generation pipeline
    response = None
    name_keywords = [
        "your name", "what is your name", "who are you", "tumhara naam", "tum kaun", "tum kaun ho", "naam kya hai", "aapka naam", "tumhara naam kya hai"
    ]

    if not response and ("what is your name" in translated_input.lower() or "your name" in translated_input.lower()):
        print("[DEBUG] Response from: Name Handler")
        response = f"My name is {CHATBOT_NAME}. What would you like to know about {CURRENT_TOPIC.lower()} safety today?"
        response = translate_response(response, lang_map.get(input_lang, 'en'), script_type)
    
    # 3. Check time-based greetings
    if not response:
        temp = handle_time_based_greeting(user_input)
        if temp:
            print("[DEBUG] Response from: Time-Based Greeting")
            response = temp
    
    # 4. Check date-related queries
    if not response:
        temp = handle_date_related_queries(user_input)
        if temp:
            print("[DEBUG] Response from: Date Handler")
            response = temp
    
    # 5. Generate NLP response
    if not response:
        temp = generate_nlp_response(user_input)
        if temp:
            print("[DEBUG] Response from: NLP Generator")
            response = temp
    
    # 6. Fallback to Mistral API
    if not response:
        temp = get_mistral_safety_response(user_input, history)
        if temp:
            print("[DEBUG] Response from: Mistral API Fallback")
            response = temp

    # 2. Check knowledge base (intents)
    if not response:
        print("[DEBUG] Response from: Knowledge Base (search_intents_and_respond_safety)")
        response = search_intents_and_respond_safety(user_input, safety_kb)
    
    # Enhance and return response
    final_response = update_and_respond_with_history(
        user_input, 
        response, 
        user=user, 
        chatbot_type='safety'
    )
    
    # Ensure conversation keeps moving forward
    if len(history) > 3 and not final_response.strip().endswith('?'):
        follow_up = get_conversation_driver(history, 'mid')
        final_response = f"{final_response} {follow_up}"
        
    lang_map = {
    'hinglish': 'hi',
    'minglish': 'mr',
    'hi': 'hi',
    'mr': 'mr'
     }

    if input_lang == 'hinglish':
        final_response = mistral_translate_response(final_response, 'hinglish')
    elif input_lang == 'minglish':
        final_response = translate_response(final_response, 'mr', 'english_script')
    elif input_lang == 'hi':
        final_response = translate_response(final_response, 'hi', 'native_script')
    elif input_lang == 'mr':
        final_response = translate_response(final_response, 'mr', 'native_script')
    # else English, no translation needed
    
    print(f"[DEBUG] Detected language variant: {input_lang}") 
    history.append({"user": user_input, "bot": final_response})
    save_session_history(history_file_path, history)

    return final_response