from .common_utils import *
import os
import json
import uuid
from django.contrib.auth import get_user_model
from .models import ChatbotConversation
import re
import requests
User = get_user_model()

MISTRAL_API_KEYS = [
    "5jMPffjLAwLyyuj6ZwFHhbLZxb2TyfUR",  # existing key
    "tZKRscT6hDUurE5B7ex5j657ZZQDQw3P",
    "3OyOnjAypy79EewldzfcBczW01mET0fM"
]

# Change the bot name here
CHATBOT_NAME = "Suraksha Mitra"

current_dir = os.path.dirname(__file__)
json_dir = os.path.join(current_dir, "json_files")

content_path = os.path.join(json_dir, "content.json")
history_file_path = os.path.join(json_dir, "session_history_gmtt.json")

if not os.path.exists(history_file_path):
    with open(history_file_path, "w") as f:
        json.dump([], f)

safety_kb = load_knowledge_base(content_path)
  # Should be <class 'dict'>

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
        # Prompt 3: Safety-Focused Conversation Driver
        prompt = f"""You assist with workplace safety only. Decline anything off-topic.

Context: {history[-2:] if history else 'New conversation'}
Query: {user_query}

Rules:
- 1 sentence reply
- Use real safety terms
- Never guess or repeat
- Occasionally end with a safety tip or question
- Unrelated? Respond: "Sorry, I can only help with workplace safety-related topics."

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
    
    history.append({"user": user_input, "bot": current_response})
    save_session_history(history_file_path, history)
    
    return current_response


def get_mistral_safety_response(user_query, history):
    try:
        # Prompt 1: General Mistral Response (with full rules, minimized)
        prompt = f"""You are a workplace safety assistant.

Your job:
1. Only answer workplace safety questions.
2. Decline all unrelated queries with: "Sorry, I can only help with workplace safety-related topics."
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

    # Prompt 2: Knowledge-Base Context Prompt (using content.json)
    prompt = f"""You are a workplace safety bot. Use only the info below to answer.

If a question isn’t about workplace safety or not covered, say:
"Sorry, I can only assist with workplace safety-related questions based on the safety guidelines I have."

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
    
    
    # Language detection and translation
    input_lang = detect_language(user_input)
    script_type = detect_input_language_type(user_input)
    translated_input = translate_to_english(user_input) if input_lang != "en" else user_input

    # Response generation pipeline
    response = None
    
    # 1. Check for name query
    if not response and ("what is your name" in translated_input.lower() or "your name" in translated_input.lower()):
        print("[DEBUG] Response from: Name Handler")
        response = f"My name is {CHATBOT_NAME}. What would you like to know about safety today?"
    
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
        
    if input_lang in ['hi', 'mr'] or 'minglish' in input_lang or 'hinglish' in input_lang:
        final_response = translate_response(final_response, input_lang, script_type)

    return final_response