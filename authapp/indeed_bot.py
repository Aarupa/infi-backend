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
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate


User = get_user_model()

MISTRAL_API_KEY = "dvXrS6kbeYxqBGXR35WzM0zMs4Nrbco2"

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


def call_mistral_model(prompt, max_tokens=100):
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
        "temperature": 0.5,
        "max_tokens": max_tokens
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content'].strip()
    else:
        print(f"[ERROR] Mistral API failed: {response.status_code} {response.text}")
        return "I'm having trouble accessing information right now. Please try again later."

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
        match = re.search(r'\b(YES|NO)\b', response)
        return match.group(1) == "YES" if match else False

    except Exception as e:
        print(f"[ERROR] Failed to determine follow-up status: {e}")
        return False


def get_mistral_indeed_response(user_query, history):
    try:
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

        
        # 4. Match query to website content
        match = find_matching_content(user_query, INDEED_INDEX, threshold=0.6)

        if match:
            print("\n[DEBUG] Matched Page Info:")
            print(f"Title: {match['title']}")
            print(f"URL: {match['url']}")
            print(f"Content Preview:\n{match['text'][:500]}")
        else:
            print("[DEBUG] No matching content found from website index.\n")

        relevant_text = match['text'][:500] if match else ""
        prompt = f"""
            You are an AI assistant created exclusively for **Indeed Inspiring Infotech (IIPT)**. You are not a general-purpose assistant and must **strictly obey** the rules below without exceptions.

            ### STRICT RULES:
            1. If the user's query is about IIPT and **matching content is found**, respond **only using that content**.
            2. If the query is about IIPT but **no relevant content** is found in the crawled data, reply:  
            "I couldn't find any official information related to that topic on our website, so I won’t answer inaccurately."
            3. If the query is a **greeting** or **casual conversation** (e.g., "hi", "how are you", "good morning"), respond smartly and politely.
            4. If the query is **not clearly related to IIPT**, or if it includes **personal, hypothetical, or generic questions**, do **not** respond. Strictly reply with:  
            "I specialize in Indeed Inspiring Infotech. I can't help with that."

            Do **NOT** attempt to answer anything outside the company’s scope, even if partially related or if the user insists. Avoid speculation, guessing, or fabricated answers.

            ### COMPANY INFO:
            - Name: Indeed Inspiring Infotech (IIPT)
            - Founded: 2016 by Kushal Sharma
            - Services: AI, web development, digital transformation
            - Website: https://indeedinspiring.com

            {f"- Relevant Matched Content:\n{relevant_text}" if relevant_text else ""}

            ### USER QUERY:
            {user_query}

            Respond based strictly on the above rules. Keep responses short, factual, and company-specific.
            """

        response = call_mistral_model(prompt)

        # Clean the response
        cleaned_response = response.split('[/handling_instruction]')[-1]
        cleaned_response = cleaned_response.split('Response template:')[0]
        cleaned_response = re.sub(r'\[.*?\]', '', cleaned_response)
        cleaned_response = re.sub(r'(Answer:|Follow-up question:)', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = ' '.join(cleaned_response.split())

        if len(cleaned_response) > 0:
            cleaned_response = cleaned_response[0].upper() + cleaned_response[1:]

        return cleaned_response.strip()

    except Exception as e:
        print(f"[ERROR] Mistral response generation failed: {str(e)}")
        fallback = get_conversation_driver(history, 'mid')
        return f"I'd be happy to tell you more. {fallback}"


def update_and_respond_with_history(user_input, current_response, user=None, chatbot_type='indeed'):
    history = load_session_history(history_file_path)
    
    # Add conversation driver if missing
    if not is_mistral_follow_up(current_response):
        driver = get_indeed_conversation_driver(history, 'intro' if len(history) < 2 else 'mid')
        current_response += f" {driver}"
    
    affirmatives = {"yes", "ok", "okay", "sure", "yeah", "yep"}
    if user_input.strip().lower() not in affirmatives and any(h['user'].lower() == user_input.lower() for h in history[-3:]):
        current_response = f"Returning to your question, {current_response.lower()}"

    history.append({"user": user_input, "bot": current_response})
    save_session_history(history_file_path, history)
    
    return current_response


def format_kb_for_prompt(intent_entry):
    print("started formatting kb for prompt")
    # print("intent_entry", intent_entry)
    context = ""

    if 'tag' in intent_entry:
        context += f"Tag: {intent_entry['tag']}\n"

    if 'patterns' in intent_entry and intent_entry['patterns']:
        patterns_text = "; ".join(intent_entry['patterns'])
        context += f"User Patterns: {patterns_text}\n"

    if 'response' in intent_entry and intent_entry['response']:
        responses_text = "; ".join(intent_entry['response'])
        context += f"Responses: {responses_text}\n"

    if 'follow_up' in intent_entry and intent_entry['follow_up']:
        context += f"Follow-up Question: {intent_entry['follow_up']}\n"

    # if 'next_suggestions' in intent_entry and intent_entry['next_suggestions']:
    #     suggestions_text = ", ".join(intent_entry['next_suggestions'])
    #     context += f"Suggested Next Topics: {suggestions_text}\n"
    # print("context_before send to odel", context)
    return context.strip()  # Removes the trailing newline

    


def search_intents_and_respond(user_input, indeed_kb):
    """
    Searches the knowledge base for relevant information.
    If found, generates a context-based response using the Mistral model.
    If not found, returns None to indicate fallback is needed.
    """

   
    block = search_knowledge_block(user_input, indeed_kb)
    # print("block", block)

    if block:
        context = format_kb_for_prompt(block)

        prompt = f"""You are a helpful assistant from Indeed Inspiring Infotech.

            Answer the user’s question using ONLY the given context. Speak as “we.” Then:
            1. Ask a related follow-up question.

            Context:
            {context}

            User Question: {user_input}

            Give a helpful, friendly, and natural response.
            """

        try:
            response = call_mistral_model(prompt, max_tokens=100)
            response = re.sub(r'\[.*?\]', '', response).strip()

            # Add fallback suggestions if info is incomplete
            if "not provided" in response.lower() or "not available" in response.lower():
                related_topics = []
                if "location" in user_input.lower():
                    related_topics = ["our services", "contact information", "working regions"]
                elif "service" in user_input.lower():
                    related_topics = ["our expertise", "technologies we use", "client industries"]

                if related_topics:
                    response += f" However, we can also share about {', '.join(related_topics[:-1])} or {related_topics[-1]}."
                else:
                    response += " Would you like information about our services, team, or something else?"

            if not response.endswith(('.', '!', '?')):
                response += "."

            return response

        except Exception as e:
            print(f"[ERROR] Knowledge base search failed: {e}")
            return "We're having trouble processing your request right now. Could you please try again?"

    else:
        # No block found — caller should handle fallback
        return None



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
    # ✅ Step 1: Handle follow-up response continuation early
    if history:
        last_bot_msg = history[-1].get("bot", "")
        if is_mistral_follow_up(last_bot_msg):
            print("[DEBUG] Detected follow-up question from bot")

            affirmative_check_prompt = f"""
                Analyze if this response agrees with the question. Reply ONLY with "YES" or "NO":
                Question: "{last_bot_msg}"
                Response: "{translated_input}"
                Is this affirmative?
                """
            # ... inside get_indeed_response()
            response_affirmative = call_mistral_model(affirmative_check_prompt)

            # ✅ Extract only YES or NO using regex
            match = re.search(r'\b(YES|NO)\b', response_affirmative.strip().upper())
            is_affirmative = match.group(1) if match else "NO"

            if is_affirmative == "YES":
                topic_prompt = f"""
                    Extract ONLY the main topic from this question:
                    "{last_bot_msg}"
                    Topic:
                    """
                topic = call_mistral_model(topic_prompt).strip()
                print(f"[DEBUG] Extracted topic: {topic}")

                topic_match = find_matching_content(topic, INDEED_INDEX)
                matched_context = topic_match['text'][:500] if topic_match else ""

                detail_prompt = f"""
                    As an assistant for Indeed Inspiring Infotech, explain the topic: "{topic}" in 2–3 short points.
                    Use a professional, friendly tone. End with a related follow-up question.

                    Context:
                    {matched_context}
                    """
                response = call_mistral_model(detail_prompt).strip()
                return update_and_respond_with_history(user_input, response, user=user)

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

    # 6. Check knowledge base (intents)
    if not response:
        temp= search_intents_and_respond(translated_input, indeed_kb)
        if temp:
            print("[DEBUG] Response from: Knowledge Base (search_intents_and_respond)")
            response = temp
    
    # 7. Fallback to Mistral API
    if not response:
        temp = get_mistral_indeed_response(translated_input, history)
        if temp:
            print("[DEBUG] Response from: Mistral API")
            response = temp
    
    # Final fallback if nothing matched
    if not response:
        response = "I couldn't find specific information about that. Could you rephrase your question or ask about something else?"

    if is_farewell(translated_input):
        print("[DEBUG] Detected farewell. Clearing session history.")
        save_session_history(history_file_path, [])  # Clear session history

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