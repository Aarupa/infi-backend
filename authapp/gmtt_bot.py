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
import time
import re

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

# def get_mistral_gmtt_response(user_query):
#     try:
#         match = find_matching_content(user_query, GMTT_INDEX, threshold=0.6)

#         best_match = None
#         best_score = 0
#         query_keywords = set(user_query.lower().split())

#         for url, data in GMTT_INDEX.items():
#             page_keywords = set(data['text'].lower().split())
#             match_score = len(query_keywords & page_keywords)
#             if match_score > best_score:
#                 best_match = data
#                 best_score = match_score

#         context = """
#         Give Me Trees Foundation is a non-profit organization founded in 1978 by Swami Prem Parivartan (Peepal Baba).
#         It focuses on environmental conservation through tree plantation, especially Peepal trees, across India.
#         Website: https://www.givemetrees.org
#         """

#         if match:
#             context += f"\n\nRelevant page content from {match['title']}:\n{match['text']}"
#             print(f"[DEBUG] Matched page title: {match['title']}")
#             print(f"[DEBUG] Matched page snippet:\n{match['text'][:500]}")

#         prompt = f"""You are an assistant for Give Me Trees Foundation and developed by Give Me Trees AIML team.

# Strict Rules:
# 1. Only provide information about Give Me Trees Foundation from the website givemetrees.org
# 2. Also handle general greetings and farewells and general conversations like hi, hello, how are you, etc.
# 3. For unrelated topics, reply that you don’t have info on that and focus only on Give Me Trees Foundation. Include the topic name in your response. Rephrase each time.
# 4. Keep responses concise (1 sentence maximum)
# 5. If needed, mention to visit givemetrees.org for more details

# Context: {context}

# User Query: {user_query}

# Response:"""

#         return call_mistral_model(prompt)

#     except Exception as e:
#         print(f"[ERROR] Mistral call failed: {e}")
#         return "I'm having trouble accessing organization information right now. Please visit givemetrees.org for details."

def get_mistral_gmtt_response(user_query, history):
    try:
        # ... existing context setup ...
        if is_contact_request(user_query):
            return (f"Please share your query/feedback/message with me and I'll "
                   f"forward it to our team at {CONTACT_EMAIL}. "
                   "Could you please tell me your name and email address?")

        # Check for user providing information
        if is_info_request(user_query):
            return ("Thank you for sharing your details! I've noted your "
                   f"information and will share it with our team at {CONTACT_EMAIL}. "
                   "Is there anything specific you'd like us to know?")
        prompt = f"""As a conversation driver for Give Me Trees Foundation, your role is to:
1. Provide accurate information
2. Actively guide the conversation forward
3. Suggest natural next steps
4. Maintain professional yet engaging tone

Recent conversation context:
{history[-2:] if history else 'New conversation'}

Current query: {user_query}

Guidelines:
- Answer concisely (1-2 sentences)
- Always end with a relevant follow-up question
- Suggest logical next topics
- Never repeat previous questions

Response template:
[Answer] [Follow-up question]"""

        response = call_mistral_model(prompt)
        
 # Inline response cleaning
        cleaned_response = response.split('[/handling_instruction]')[-1]  # Remove metadata
        cleaned_response = cleaned_response.split('Response template:')[0]  # Remove templates
        cleaned_response = re.sub(r'\[.*?\]', '', cleaned_response)  # Remove any [tags]
        cleaned_response = re.sub(r'(Answer:|Follow-up question:)', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = ' '.join(cleaned_response.split())  # Normalize whitespace
        
        # Ensure proper capitalization
        if len(cleaned_response) > 0:
            cleaned_response = cleaned_response[0].upper() + cleaned_response[1:]
            
        return cleaned_response.strip()

    except Exception as e:
        driver = get_conversation_driver(history, 'mid')
        return f"I'd be happy to tell you more. {driver}"

# def update_and_respond_with_history(user_input, current_response, user=None, chatbot_type='gmtt'):
#     exit_keywords = ["bye", "bye bye", "exit"]
#     history = load_session_history(history_file_path)
#     print(f"[HISTORY] Loaded {len(history)} items from JSON file.")

#     if any(kw in user_input.lower() for kw in exit_keywords):
#         print("[HISTORY] Exit keyword detected. Attempting to save session to DB...")
        
#         store_session_in_db(history, user, chatbot_type)
#         print("[HISTORY] Session saved to DB. Clearing history file.")
#         open(history_file_path, "w").close()
#         print("[HISTORY] Cleared session history JSON file.")
#         return current_response
    
#     history_text = ""
#     for turn in history[-5:]:
#         history_text += f"User: {turn['user']}\nBot: {turn['bot']}\n"

#     prompt = f"""
# You are a smart assistant representing Give Me Trees Foundation.

# Use the conversation history below and the current system reply to generate a final response.

# Rules:
# 1. By default, keep your responses concise and limited to 1 sentence.
# 2. If the user has asked a similar or identical question earlier, start with something like \"As I mentioned earlier,\" and give a slightly expanded or rephrased version of the previous answer.
# 3. Keep responses concise (1 sentence maximum), but only if the topic has already been discussed before.
# 4. Keep responses natural, helpful, and non-repetitive.

# Conversation History:
# {history_text}

# Current System Response:
# {current_response}

# Final Answer:
# """
#     try:
#         final_response = call_mistral_model(prompt, max_tokens=250)
#         history.append({"user": user_input, "bot": final_response})
#         save_session_history(history_file_path, history)
#         return final_response
#     except Exception as e:
#         print(f"[ERROR] History response generation failed: {e}")
#         history.append({"user": user_input, "bot": current_response})
#         save_session_history(history_file_path, history)
#         return current_response

# def update_and_respond_with_history(user_input, current_response, user=None, chatbot_type='gmtt'):
#     exit_keywords = ["bye", "bye bye", "exit"]
#     history = load_session_history(history_file_path)
    
#     # Add conversational enhancements
#     current_response = vary_response_length(current_response)
#     if random.random() < 0.1:
#         current_response = add_occasional_typos(current_response)
    
#     if any(kw in user_input.lower() for kw in exit_keywords):
#         store_session_in_db(history, user, chatbot_type)
#         open(history_file_path, "w").close()
        
#         farewell = random.choice([
#             "It was great talking with you!",
#             "Have a wonderful day!",
#             "Hope to chat again soon!"
#         ])
#         return f"{current_response} {farewell}"
    
#     # Add proactive conversation driving
#     if len(history) % 3 == 0:  # Every 3 turns
#         follow_up = get_proactive_question(history)
#         if follow_up and "?" in follow_up:
#             current_response = f"{current_response} {follow_up}"
    
#     history.append({"user": user_input, "bot": current_response})
#     save_session_history(history_file_path, history)
    
#     simulate_typing_delay(current_response)
    
#     return current_response

def update_and_respond_with_history(user_input, current_response, user=None, chatbot_type='gmtt'):
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

def search_intents_and_respond(user_input, gmtt_kb):
    """
    Uses Mistral API to answer ONLY using content from trees.json (gmtt_kb).
    Always take initiative to keep the conversation going and make it look natural.
    Always use 'we' instead of 'they' when referring to the organization or its services, and answer as if you are part of Give Me Trees Foundation.
    """
    # Flatten all content from gmtt_kb into a single context string
    context = ""
    if isinstance(gmtt_kb, dict):
        for key, value in gmtt_kb.items():
            if isinstance(value, dict):
                for subkey, subval in value.items():
                    context += f"{subkey}: {subval}\n"
            else:
                context += f"{key}: {value}\n"
    elif isinstance(gmtt_kb, list):
        for item in gmtt_kb:
            context += f"{item}\n"
    else:
        context = str(gmtt_kb)

    prompt = f"""You are an expert assistant and a part of the Give Me Trees Foundation team. 
Answer the user's question ONLY using the information below.
Always use 'we' instead of 'they' when referring to the organization or its services, and answer as if you are part of Give Me Trees Foundation.
If the answer is not present, reply: "Sorry, I can only answer questions based on the provided information."
Always take initiative to keep the conversation going and make it look natural, by asking a relevant follow-up question or inviting the user to continue.

---START OF INFORMATION---
{context}
---END OF INFORMATION---

User question: {user_input}
Answer:"""

    response = call_mistral_model(prompt, max_tokens=200)
    # Clean up any hallucinated instructions
    response = re.sub(r'\[.*?\]', '', response)
    return response.strip()

def get_gmtt_response(user_input, user=None):
    print("hel")
    print(type(gmtt_kb))
    # Input validation
    if not user_input or not isinstance(user_input, str) or len(user_input.strip()) == 0:
        return "Please provide a valid input."

    # Load conversation history
    history = load_session_history(history_file_path)
    if history and "please tell me your name" in history[-1]["bot"].lower():
        return handle_user_info_submission(user_input)
    
    # Language detection and translation
    input_lang = detect_language(user_input)
    script_type = detect_input_language_type(user_input)
    translated_input = translate_to_english(user_input) if input_lang != "en" else user_input

    # Response generation pipeline
    response = None
    
    # 1. Check for name query
    if not response and ("what is your name" in translated_input.lower() or "your name" in translated_input.lower()):
        response = f"My name is {CHATBOT_NAME}. What would you like to know about Give Me Trees Foundation today?"
    
    # 2. Check knowledge base (intents)
    if not response:
        print("hii")
        response = search_intents_and_respond(user_input, gmtt_kb)
    
    # 3. Check time-based greetings
    if not response:
        response = handle_time_based_greeting(user_input)
    
    # 4. Check date-related queries
    if not response:
        response = handle_date_related_queries(user_input)
    
    # 5. Generate NLP response
    if not response:
        response = generate_nlp_response(user_input)
    
    # 6. Fallback to Mistral API
    if not response:
        response = get_mistral_gmtt_response(user_input, history)
    
    # Enhance and return response
    final_response = update_and_respond_with_history(
        user_input, 
        response, 
        user=user, 
        chatbot_type='gmtt'
    )
    
    # Ensure conversation keeps moving forward
    if len(history) > 3 and not final_response.strip().endswith('?'):
        follow_up = get_conversation_driver(history, 'mid')
        final_response = f"{final_response} {follow_up}"
    
    return response

def handle_user_info_submission(user_input):
    """Process user contact information"""
    # Extract name and email (simple pattern matching)
    name = re.findall(r"(?:my name is|i am|name is)\s+([A-Za-z ]+)", user_input, re.IGNORECASE)
    email = re.findall(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", user_input.lower())
    
    response = []
    if name:
        response.append(f"Thank you {name[0].strip()}!")
    if email:
        response.append("I've noted your email address.")
    
    if not response:
        response.append("Thank you for sharing your details!")
    
    response.append(
        f"I'll share your information with our team at {CONTACT_EMAIL}. "
        "We'll get back to you soon. Is there anything else I can help with?"
    )
    
    # Here you would actually store/send the information
    # store_contact_info(name[0] if name else None, email[0] if email else None)
    
    return ' '.join(response)