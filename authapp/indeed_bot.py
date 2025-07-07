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

# Replace single API key with a list of keys
MISTRAL_API_KEYS = [
    "ybRkqE9GJxcSe4WAYRVLCknholZJnLtM",  # our key
    "dvXrS6kbeYxqBGXR35WzM0zMs4Nrbco2", # Gayatri's key
    "3rd_KEY_HERE",
    "4th_KEY_HERE",
    "5th_KEY_HERE"
]

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


# Update call_mistral_model to use key rotation and enhanced error handling
def call_mistral_model(prompt, max_tokens=100):
    url = "https://api.mistral.ai/v1/chat/completions"
    headers_template = {
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

    for idx, key in enumerate(MISTRAL_API_KEYS):
        headers = headers_template.copy()
        headers["Authorization"] = f"Bearer {key}"

        print(f"[DEBUG] Trying Mistral API key #{idx+1}: {key[:6]}...")

        try:
            response = requests.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                print(f"[DEBUG] API call succeeded with key #{idx+1}")
                return response.json()['choices'][0]['message']['content'].strip()
            
            elif response.status_code == 401:
                print(f"[WARNING] Key #{idx+1} is unauthorized or expired. Trying next key.")
                continue
            
            elif response.status_code == 429:
                print(f"[WARNING] Key #{idx+1} is rate-limited. Trying next key.")
                continue

            else:
                print(f"[ERROR] Mistral API call failed with status {response.status_code}: {response.text}")
                continue

        except requests.exceptions.RequestException as e:
            print(f"[EXCEPTION] Request failed for key #{idx+1}: {e}")
            continue

    print("[CRITICAL] All Mistral API keys failed.")
    return "I'm having trouble accessing information right now. Please try again later."


# def get_mistral_indeed_response(user_query):
#     try:
#         match = find_matching_content(user_query, INDEED_INDEX, threshold=0.6)

#         best_match = None
#         best_score = 0
#         query_keywords = set(user_query.lower().split())

#         for url, data in INDEED_INDEX.items():
#             page_keywords = set(data['text'].lower().split())
#             match_score = len(query_keywords & page_keywords)
#             if match_score > best_score:
#                 best_match = data
#                 best_score = match_score

#         context = """
#         Indeed Inspiring Infotech is a technology company providing innovative IT solutions.
#         Key Information:
#         - Founded by Kushal Sharma in 2016
#         - Specializes in AI, web development, and digital transformation
#         - Website: https://indeedinspiring.com
#         """

#         if match:
#             context += f"\n\nRelevant page content from {match['title']}:\n{match['text']}"
#             print(f"[DEBUG] Matched page title: {match['title']}")
#             print(f"[DEBUG] Matched page snippet:\n{match['text'][:500]}")

#         prompt = f"""You are an assistant for Indeed Inspiring Infotech and developed by Indeed Inspiring AIML team.

# Strict Rules:
# 1. Only provide information about Indeed Inspiring Infotech from the website indeedinspiring.com
# 2. Also handle general greetings and farewells and general conversations like hi, hello, how are you, etc.
# 3. For unrelated topics, reply that you don’t have info on that and focus only on Indeed Inspiring Infotech. Include the topic name in your response. Rephrase each time.
# 4. Keep responses concise (1 sentence maximum)
# 5. If needed, mention to visit indeedinspiring.com for more details

# Context: {context}

# User Query: {user_query}

# Response:"""

#         return call_mistral_model(prompt)

#     except Exception as e:
#         print(f"[ERROR] Mistral call failed: {e}")
#         return "I'm having trouble accessing company information right now. Please visit indeedinspiring.com for details."

#----------------


# def get_mistral_indeed_response(user_query, history):
#     try:
#         # ... existing context setup ...
#         if is_contact_request(user_query):
#             return (f"Please share your query/feedback/message with me and I'll "
#                    f"forward it to our team at {CONTACT_EMAIL}. "
#                    "Could you please tell me your name and email address?")

#         # Check for user providing information
#         if is_info_request(user_query):
#             return ("Thank you for sharing your details! I've noted your "
#                    f"information and will share it with our team at {CONTACT_EMAIL}. "
#                    "Is there anything specific you'd like us to know?")
#         prompt = f"""As a conversation driver for Give Me Trees Foundation, your role is to:
# 1. Provide accurate information
# 2. Actively guide the conversation forward
# 3. Suggest natural next steps
# 4. Maintain professional yet engaging tone

# Recent conversation context:
# {history[-2:] if history else 'New conversation'}

# Current query: {user_query}

# Guidelines:
# - Answer concisely (1-2 sentences)
# - Always end with a relevant follow-up question
# - Suggest logical next topics
# - Never repeat previous questions

# Response template:
# [Answer] [Follow-up question]"""

#         response = call_mistral_model(prompt)
        
#  # Inline response cleaning
#         cleaned_response = response.split('[/handling_instruction]')[-1]  # Remove metadata
#         cleaned_response = cleaned_response.split('Response template:')[0]  # Remove templates
#         cleaned_response = re.sub(r'\[.*?\]', '', cleaned_response)  # Remove any [tags]
#         cleaned_response = re.sub(r'(Answer:|Follow-up question:)', '', cleaned_response, flags=re.IGNORECASE)
#         cleaned_response = ' '.join(cleaned_response.split())  # Normalize whitespace
        
#         # Ensure proper capitalization
#         if len(cleaned_response) > 0:
#             cleaned_response = cleaned_response[0].upper() + cleaned_response[1:]
            
#         return cleaned_response.strip()

#     except Exception as e:
#         driver = get_indeed_conversation_driver(history, 'mid')
#         return f"I'd be happy to tell you more. {driver}"
def is_mistral_follow_up(bot_message: str) -> bool:
   
    prompt = f"""
You are an expert in analyzing chatbot conversations.

Determine if the following chatbot message is a follow-up question.

Definition:
A follow-up question encourages the user to respond with interest, elaboration, or permission to continue.
It may sound like: "Would you like to know more?", "Shall I explain further?", or "Do you want details?"

Chatbot message:
"{bot_message}"

Answer only with "YES" or "NO".
"""

    try:
        response = call_mistral_model(prompt).strip().upper()
        return response == "YES"
    except Exception as e:
        print(f"[ERROR] Failed to determine follow-up status: {e}")
        return False


def get_mistral_indeed_response(user_query, history):
    """
    Enhanced Indeed Inspiring Infotech response handler that:
    1. Maintains all existing functionality (contact requests, info handling)
    2. Adds smart affirmative response detection
    3. Provides contextual follow-ups
    4. Includes robust error handling
    """
    try:
        # --- Existing Core Functionality ---
        # 1. Handle contact requests
        if is_contact_request(user_query):
            return (f"Please share your query/feedback/message with me and I'll "
                   f"forward it to our team at {CONTACT_EMAIL}. "
                   "Could you please tell me your name and email address?")

        # 2. Handle user information submissions
        if is_info_request(user_query):
            return ("Thank you for sharing your details! I've noted your "
                   f"information and will share it with our team at {CONTACT_EMAIL}. "
                   "Is there anything specific you'd like us to know?")

        # --- New Affirmative Response Handling ---
        if history:  # Only check if there's conversation history
            last_bot_question = history[-1]["bot"]
            
            # Check if this appears to be a response to a follow-up question
            is_follow_up = is_mistral_follow_up(last_bot_question)
            
            if is_follow_up:
                # Ask Mistral to determine if this is affirmative
                affirmative_check_prompt = f"""
                Analyze if this response agrees with the question. Reply ONLY with "YES" or "NO":
                
                Question: "{last_bot_question}"
                Response: "{user_query}"
                
                Is this affirmative?"""
                
                mistral_verdict = call_mistral_model(affirmative_check_prompt).strip().upper()
                
                if mistral_verdict == "YES":
                    # Extract the topic being referenced
                    topic_prompt = f"""
                    Extract ONLY the main topic from this question:
                    "{last_bot_question}"
                    
                    Examples:
                    - "Want to know about our AI solutions?" → "AI solutions"
                    - "Interested in our team?" → "team"
                    
                    Topic: """
                    
                    topic = call_mistral_model(topic_prompt).strip()
                    
                    if topic:
                        # Generate detailed response
                        detail_prompt = f"""
                        As Indeed Inspiring Infotech's assistant, provide:
                        1. 2-3 key points about {topic}
                        2. Professional but conversational tone
                        3. End with relevant follow-up
                        
                        Context: {INDEED_INDEX.get('about', '')[:500]}"""
                        
                        detailed_response = call_mistral_model(detail_prompt)
                        return detailed_response

        # --- Default Conversation Flow ---
        # Prepare context for Mistral
        context = f"""
        Indeed Inspiring Infotech specializes in:
        - AI Solutions
        - Web Development
        - Digital Transformation
        Website: https://indeedinspiring.com
        
        Conversation History:
        {history[-2:] if history else 'New conversation'}
        """
        
        prompt = f"""As Indeed Inspiring Infotech's assistant, respond to:
        "{user_query}"
        
        Guidelines:
        1. Use ONLY company information
        2. Keep responses concise (1-2 sentences)
        3. Maintain professional tone
        4. End with relevant follow-up question
        
        Context: {context}"""
        
        response = call_mistral_model(prompt)
        
        # --- Response Cleaning ---
        # Remove any metadata/templates
        cleaned_response = response.split('[/handling_instruction]')[-1]
        cleaned_response = cleaned_response.split('Response template:')[0]
        
        # Clean formatting artifacts
        cleaned_response = re.sub(r'\[.*?\]', '', cleaned_response)
        cleaned_response = re.sub(r'(Answer:|Follow-up question:)', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = ' '.join(cleaned_response.split())
        
        # Ensure proper capitalization
        if len(cleaned_response) > 0:
            cleaned_response = cleaned_response[0].upper() + cleaned_response[1:]
            
        return cleaned_response.strip()

    except Exception as e:
        print(f"[ERROR] Mistral response generation failed: {str(e)}")
        # Graceful fallback
        return get_indeed_conversation_driver(history, 'mid') if history else "I'd be happy to help. What would you like to know?"
    
def update_and_respond_with_history(user_input, current_response, user=None, chatbot_type='gmtt'):
    history = load_session_history(history_file_path)
    
    # Add conversation driver if missing
    if not any(punct in current_response[-1] for punct in ['?', '!']):
        driver = get_indeed_conversation_driver(history, 
                                      'intro' if len(history) < 2 else 'mid')
        current_response = f"{current_response} {driver}"
    
    # Ensure varied responses for repeated questions
    if any(h['user'].lower() == user_input.lower() for h in history[-3:]):
        current_response = f"Returning to your question, {current_response.lower()}"
    
    history.append({"user": user_input, "bot": current_response})
    save_session_history(history_file_path, history)
    
    return current_response
    
# def search_intents_and_respond(user_input, indeed_kb):
#     """
#     Uses knowledge base to answer questions about Indeed Inspiring Infotech.
#     Provides helpful responses even when exact information isn't available.
#     Maintains natural conversation flow and suggests related topics.
#     """
#     # Flatten knowledge base content
#     context = ""
#     if isinstance(indeed_kb, dict):
#         for key, value in indeed_kb.items():
#             if isinstance(value, dict):
#                 for subkey, subval in value.items():
#                     context += f"{subkey}: {subval}\n"
#             else:
#                 context += f"{key}: {value}\n"
#     elif isinstance(indeed_kb, list):
#         for item in indeed_kb:
#             context += f"{item}\n"
#     else:
#         context = str(indeed_kb)

#     prompt = f"""You are a helpful assistant representing Indeed Inspiring Infotech.
# Follow these guidelines strictly:
# 1. Use ONLY the information below to answer
# 2. Always speak as "we" (first-person plural)
# 3. If information isn't available:
#    - Acknowledge the question
#    - Explain what you CAN share
#    - Suggest related information
# 4. Keep responses conversational and helpful

# Available Information:
# {context}

# User Question: {user_input}
# Provide a helpful response:"""

#     try:
#         response = call_mistral_model(prompt, max_tokens=100)
        
#         # Clean and enhance the response
#         response = re.sub(r'\[.*?\]', '', response).strip()
        
#         # If response indicates missing info, make it more helpful
#         if "not provided" in response.lower() or "not available" in response.lower():
#             # Identify related topics from context that might help
#             related_topics = []
#             if "location" in user_input.lower():
#                 related_topics = ["our services", "contact information", "working regions"]
#             elif "service" in user_input.lower():
#                 related_topics = ["our expertise", "technologies we use", "client industries"]
            
#             if related_topics:
#                 response += f" However, I can tell you about {', '.join(related_topics[:-1])} or {related_topics[-1]}."
#             else:
#                 response += " Would you like information about our services, team, or something else?"
        
#         # Ensure response ends properly
#         if not response.endswith(('.','!','?')):
#             response += "."
            
#         return response

#     except Exception as e:
#         print(f"[ERROR] Knowledge base search failed: {e}")
#         return "I'm having trouble accessing that information. Please try asking something else about Indeed Inspiring Infotech."

from difflib import SequenceMatcher

def search_intents_and_respond(user_input, indeed_kb):
    """
    Uses knowledge base to answer questions about Indeed Inspiring Infotech.
    Now also returns a confidence score based on query similarity.
    """
    # Flatten knowledge base content and calculate match score
    context = ""
    match_score = 0.0
    input_lower = user_input.lower()

    if isinstance(indeed_kb, dict):
        for key, value in indeed_kb.items():
            if isinstance(value, dict):
                for subkey, subval in value.items():
                    context += f"{subkey}: {subval}\n"
                    sim = SequenceMatcher(None, input_lower, subkey.lower()).ratio()
                    match_score = max(match_score, sim)
            else:
                context += f"{key}: {value}\n"
                sim = SequenceMatcher(None, input_lower, key.lower()).ratio()
                match_score = max(match_score, sim)
    elif isinstance(indeed_kb, list):
        for item in indeed_kb:
            context += f"{item}\n"
            sim = SequenceMatcher(None, input_lower, item.lower()).ratio()
            match_score = max(match_score, sim)
    else:
        context = str(indeed_kb)

    prompt = f"""You are a helpful assistant representing Indeed Inspiring Infotech.
Follow these guidelines strictly:
1. Use ONLY the information below to answer
2. Always speak as "we" (first-person plural)
3. If information isn't available:
   - Acknowledge the question
   - Explain what you CAN share
   - Suggest related information
4. Keep responses conversational and helpful

Available Information:
{context}

User Question: {user_input}
Provide a helpful response:"""

    try:
        response = call_mistral_model(prompt, max_tokens=100)
        
        # Clean and enhance the response
        response = re.sub(r'\[.*?\]', '', response).strip()
        
        # If response indicates missing info, make it more helpful
        if "not provided" in response.lower() or "not available" in response.lower():
            # Identify related topics from context that might help
            related_topics = []
            if "location" in input_lower:
                related_topics = ["our services", "contact information", "working regions"]
            elif "service" in input_lower:
                related_topics = ["our expertise", "technologies we use", "client industries"]
            
            if related_topics:
                response += f" However, I can tell you about {', '.join(related_topics[:-1])} or {related_topics[-1]}."
            else:
                response += " Would you like information about our services, team, or something else?"
        
        # Ensure proper punctuation
        if not response.endswith(('.', '!', '?')):
            response += "."

        return response, match_score

    except Exception as e:
        print(f"[ERROR] Knowledge base search failed: {e}")
        return "I'm having trouble accessing that information. Please try asking something else about Indeed Inspiring Infotech.", 0.0


def get_indeed_response(user_input, user=None):
    # Input validation
    if not user_input or not isinstance(user_input, str) or len(user_input.strip()) == 0:
        return "Please provide a valid input."

    # Load conversation history
    history = load_session_history(history_file_path)
    if history and "please tell me your name" in history[-1]["bot"].lower():
        print("[DEBUG] Response from: handle_user_info_submission")
        return handle_user_info_submission(user_input)
    
    # Language detection and translation
    input_lang = detect_language(user_input)
    script_type = detect_input_language_type(user_input)
    translated_input = translate_to_english(user_input) if input_lang != "en" else user_input

    # Response generation pipeline
    response = None
    
    # 1. Check for name query
    if not response and ("what is your name" in translated_input.lower() or "your name" in translated_input.lower()):
        print("[DEBUG] Response from: Name Handler")
        response = f"My name is {CHATBOT_NAME}. What would you like to know about Indeed Inspiring Infotech today?"
    
    # 2. Check meta questions
    if not response:
        temp = handle_meta_questions(translated_input)
        if temp:
            print("[DEBUG] Response from: Meta Question Handler")
            response = temp
    
    # 3. Check time-based greetings
    if not response:
        temp = handle_time_based_greeting(translated_input)
        if temp:
            print("[DEBUG] Response from: Time-Based Greeting")
            response = temp
    
    # 4. Check date-related queries
    if not response:
        temp = handle_date_related_queries(translated_input)
        if temp:
            print("[DEBUG] Response from: Date Handler")
            response = temp
    
    # 5. Generate NLP response
    if not response:
        temp = generate_nlp_response(translated_input)
        if temp:
            print("[DEBUG] Response from: NLP Generator")
            response = temp
    
    # # 6. Check knowledge base (intents)
    # if not response:
    #     print("[DEBUG] Response from: Knowledge Base (search_intents_and_respond)")
    #     response = search_intents_and_respond(translated_input, indeed_kb)
    # 6. Check knowledge base (intents) with confidence check
    if not response:
        kb_response, kb_score = search_intents_and_respond(translated_input, indeed_kb)
        if kb_response and kb_score > 0.6:
            print(f"[DEBUG] Response from: Knowledge Base (score={kb_score:.2f})")
            response = kb_response

    # 7. Fallback to Mistral API
    if not response:
        temp = get_mistral_indeed_response(translated_input, history)
        if temp:
            print("[DEBUG] Response from: Mistral API")
            response = temp
    
    # # Final fallback if nothing matched
    # if not response:
    #     response = "I couldn't find specific information about that. Could you rephrase your question or ask about something else?"

    # Enhance and return response
    final_response = update_and_respond_with_history(
        user_input, 
        response, 
        user=user, 
        chatbot_type='indeed'
    )
    
    # Ensure conversation keeps moving forward
    if len(history) > 3 and not final_response.strip().endswith('?'):
        follow_up = get_indeed_conversation_driver(history, 'mid')
        final_response = f"{final_response} {follow_up}"
    
    return final_response

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