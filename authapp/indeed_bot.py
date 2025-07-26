from numpy import block
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
from .website_guide import get_website_guide_response, query_best_link
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

User = get_user_model()

CHATBOT_NAME = "Infi"

current_dir = os.path.dirname(__file__)
json_dir = os.path.join(current_dir, "json_files")

greetings_path = os.path.join(json_dir, "greetings.json")
farewells_path = os.path.join(json_dir, "farewells.json")
general_path = os.path.join(json_dir, "general.json")
content_path = os.path.join(json_dir, "content.json")
history_file_path = os.path.join(json_dir, "session_history_iipt.json")

if not os.path.exists(history_file_path):
    with open(history_file_path, "w") as f:
        json.dump([], f)

greetings_kb = load_json_data(greetings_path).get("greetings", {})
farewells_kb = load_json_data(farewells_path).get("farewells", {})
general_kb = load_json_data(general_path).get("general", {})
indeed_kb = load_knowledge_base(content_path)


def mistral_translate_response(response_text, target_lang_code):
    if target_lang_code == 'hinglish':
        prompt = f"""Translate the following English text about Indeed Inspiring Infotech to clear and natural Hindi written in English letters (Hinglish).
            Follow these rules strictly:
            1. Keep it short (1-2 sentences max) and easy to understand
            2. Use common Hindi words with English tech terms like "software", "development", "company"
            3. Sound professional but friendly
            4. Never add explanations or notes about the translation
            5. Maintain the original meaning exactly

            Input Text to Translate:
            {response_text}

            Translated Hinglish Output:"""
    elif target_lang_code == 'minglish':
        prompt = f"""Translate the following English text about Indeed Inspiring Infotech to clear and natural Marathi written in English letters (Minglish).
            Follow these rules strictly:
            1. Keep it short (1-2 sentences max) and easy to understand
            2. Use common Marathi words with English tech terms
            3. Sound professional but friendly
            4. Never add explanations or notes about the translation
            5. Maintain the original meaning exactly

            Input Text to Translate:
            {response_text}

            Translated Minglish Output:"""
    else:
        return response_text

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

# def crawl_indeed_website():
#     print("[DEBUG] crawl_indeed_website() called")
#     global INDEED_INDEX
#     INDEED_INDEX = crawl_website("https://indeedinspiring.com", max_pages=100)
#     print(f"[INFO] Crawled {len(INDEED_INDEX)} pages from indeedinspiring.com")
#     return INDEED_INDEX

# INDEED_INDEX = crawl_indeed_website()

def load_qa_pairs_from_file(relative_path):
    try:
        base_dir = os.path.dirname(__file__)
        file_path = os.path.join(base_dir, relative_path)

        print("[DEBUG] Loading Q&A from:", file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        qa_pairs = re.findall(r"\*\*(.*?)\*\*\s*([\s\S]*?)(?=\n\*\*|$)", content)
        formatted_pairs = [(q.strip(), a.strip()) for q, a in qa_pairs]
        print(f"[DEBUG] Loaded {len(formatted_pairs)} Q&A pairs")
        return formatted_pairs

    except Exception as e:
        print("[ERROR] Failed to load Q&A pairs:", str(e))
        return []

def format_qa_for_prompt(pairs):
    return "\n".join([f"Q: {q}\nA: {a}" for q, a in pairs])

def get_mistral_indeed_response(user_query, history):
    try:
        if is_contact_request(user_query):
            return (f"Please share your query/feedback/message with me and I'll "
                    f"forward it to our team at {CONTACT_EMAIL}. "
                    "Could you please tell me your name and email address?")

        if is_info_request(user_query):
            return ("Thank you for sharing your details! I've noted your "
                    f"information and will share it with our team at {CONTACT_EMAIL}. "
                    "Is there anything specific you'd like us to know?")

        match = find_matching_content(user_query, INDEED_INDEX, threshold=0.6)
        print("match", match)
        if match:
            relevant_text = match['text'][:500]
        else:
            relevant_text = ""

        qa_pairs = load_qa_pairs_from_file(os.path.join('json_files', 'INDEED_Follow-up_questions.txt'))
        qa_prompt = format_qa_for_prompt(qa_pairs)
    
        prompt = f"""
You are an AI assistant created for **Indeed Inspiring Infotech**. You must follow the strict rules below.

### STRICT RULES:
1. If the query matches any Q&A from the provided list, respond with the answer.
2. If the user query relates to IIPT but no match is found, say:  
   "I couldn't find any official information related to that topic on our website or files, so I won't answer inaccurately."
3. If the query is a greeting or casual talk (e.g., "hi", "how are you"), respond politely.
4. If it's not clearly related to IIPT, reply:  
   "I specialize in Indeed Inspiring Infotech. I can't help with that."

### Website Content (if any):
{relevant_text if relevant_text else '[No relevant content found]'}

### Known Q&A from Company Files:
{qa_prompt}

### User Query:
{user_query}

Respond only using the above information. Do not fabricate or guess. Keep it short, factual, and aligned with the company's official content.
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
        import traceback
        print("[ERROR] Exception caught in get_mistral_indeed_response")
        print("Error:", str(e))
        traceback.print_exc()
        print("conversion_driver_called_from_get_mistral_indeed")
        driver = get_indeed_conversation_driver(history, 'mid')
        return f"I'd be happy to tell you more. {driver}"

def handle_meta_questions(user_input):
    meta_phrases = [
        "what can i ask you", "suggest me some topics", "what topics can i ask",
        "how can you help", "what do you know", "what programs do you run",
        "what questions can i ask", "what information do you have",
        "what can you tell me", "what should i ask"
    ]
    
    lowered = user_input.lower()
    if any(phrase in lowered for phrase in meta_phrases):
        responses = [
            f"I'm here to help with all things related to Indeed Inspiring Infotech! "
            "You can ask me about our services, technologies, team, or how to collaborate with us.",
            
            "As an IIPT assistant, I can tell you about our software solutions, "
            "AI projects, development methodologies, and career opportunities. "
            "What would you like to know?",
            
            "Happy to help! You can ask about: "
            "- Our technology stack\n"
            "- Client success stories\n"
            "- How we approach projects\n"
            "- Career and internship opportunities\n"
            "What interests you most?",
            
            "I specialize in information about Indeed Inspiring Infotech's technology services. "
            "You might ask about:\n"
            "- Our founder Kushal Sharma\n"
            "- Our development process\n"
            "- Case studies from our projects\n"
            "- Upcoming hiring drives",
            
            "Let me suggest some topics:\n"
            "• Our expertise in AI and machine learning\n"
            "• How we ensure project success\n"
            "• Stories from our development team\n"
            "• Our training programs\n"
            "Which would you like to explore?"
        ]
        return random.choice(responses)
    return None

def update_and_respond_with_history(user_input, current_response, user=None, chatbot_type='indeed', context_mode=False, response_meta=None):
    history = load_session_history(history_file_path)
    
    bot_msg_1 = history[-2]["bot"] if len(history) >= 2 else ""
    bot_msg_2 = history[-1]["bot"] if len(history) >= 1 else ""
    
    is_contextual = False
    
    meta = response_meta or {}
    from_kb = meta.get('_from_kb', False)
    from_any_fun = meta.get('from_any_fun', False)
    print(f"[DEBUG] Contextual: {is_contextual}, From KB: {from_kb}, From Any Fun: {from_any_fun}")
    
    if any(h['user'].lower() == user_input.lower() for h in history[-3:]):
        current_response = f"Returning to your question, {current_response.lower()}"
    
    should_add_driver = (
            not from_kb and
            from_any_fun
    )

    print(f"[DEBUG] Should add driver: {should_add_driver}")
    
    if should_add_driver:
        print("should_add_driver is True")
        driver_type = 'intro' if len(history) < 2 else 'mid'
        driver = get_indeed_conversation_driver(history, driver_type)
        current_response = f"{current_response} {driver}"
    
    history_entry = {
        "user": user_input.strip(),
        "bot": current_response.strip(),
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "from_kb": from_kb,
            "from_any_fun": from_any_fun,
            "context_mode": context_mode
        }
    }
    
    history.append(history_entry)
    save_session_history(history_file_path, history)
    
    return current_response

def format_kb_for_prompt(intent_entry):
    print("started formatting kb for prompt")
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

    return context.strip()

def search_intents_and_respond(user_input, indeed_kb):
    block = search_knowledge_block(user_input, indeed_kb)
    
    if block:
        
        context = format_kb_for_prompt(block)
        prompt = f"""You are a helpful assistant from Indeed Inspiring Infotech.

Answer the user's question using ONLY the given context. Speak as "we." Then:
1. Ask a related follow-up question but not mention followup word.

Context:
{context}

User Question: {user_input}

Give a helpful, friendly, and natural response.
"""

        try:
            response = call_mistral_model(prompt, max_tokens=100)
            response = re.sub(r'\[.*?\]', '', response).strip()

            if "not provided" in response.lower() or "not available" in response.lower():
                related_topics = []
                if "software" in user_input.lower():
                    related_topics = ["our development process", "technologies we use", "project methodologies"]
                elif "career" in user_input.lower():
                    related_topics = ["open positions", "internship programs", "company culture"]

                if related_topics:
                    response += f" However, we can also share about {', '.join(related_topics[:-1])} or {related_topics[-1]}."
                else:
                    response += " Would you like information about our services, careers, or something else?"

            if not response.endswith(('.', '!', '?')):
                response += "."

            return response

        except Exception as e:
            print(f"[ERROR] Knowledge base search failed: {e}")
            return "We're having trouble processing your request right now. Could you please try again?"
    else:
        return None

def is_mistral_contextual_follow_up(bot_msg_1: str, bot_msg_2: str, user_input: str) -> bool:
    prompt = f"""
    Determine if the user's message is a contextually related continuation of the previous conversation.
    
    Instructions:
    - Consider if the user is following up on **either** of the last two bot messages.
    - Accept responses that show interest, ask related questions, or refer back to earlier topics.
    - Ignore responses that are clearly off-topic, unrelated, or start a new conversation.
    
    ---
    Bot Message 1 (Earlier): "{bot_msg_1}"
    Bot Message 2 (Latest): "{bot_msg_2}"
    User Input: "{user_input}"
    ---

    Respond ONLY with:
    - "CONTEXTUAL_FOLLOW_UP" → if the user input relates to either bot message.
    - "NOT_CONTEXTUAL" → if the input is off-topic or unrelated.
    """

    try:
        response = call_mistral_model(prompt).strip().upper()
        if "CONTEXTUAL_FOLLOW_UP" in response:
            return True
        elif "NOT_CONTEXTUAL" in response:
            return False
        else:
            return False
    except Exception as e:
        print(f"[ERROR] Failed to evaluate contextual follow-up: {e}")
        return False

def handle_follow_up_question(history, translated_input, user_input, user, response_meta=None):
    last_bot_msg = history[-1].get("bot", "")
    previous_bot_msg = history[-2]["bot"] if len(history) >= 2 else ""
    previous_user_msg = history[-2]["user"] if len(history) >= 2 else ""

    if not is_mistral_contextual_follow_up(previous_bot_msg, last_bot_msg, user_input):
        return None

    print("[DEBUG] Detected contextual follow-up from user")
    topic = extract_topic_of_interest(previous_bot_msg, last_bot_msg, user_input)
    print(f"[DEBUG] Extracted topic: {topic}")

    if not topic:
        print("[DEBUG] Topic not found.")
        return None

    print("topic:", topic)
    response = get_indeed_response(topic, user=None, context_mode=True, response_meta=response_meta)
    return response

def extract_topic_of_interest(bot_msg_1, bot_msg_2, user_input):
    prompt = f"""
    Your task is to extract the main topic of interest from the following conversation.

    Rules:
    1. Focus mainly on the Latest Bot Message and the User Response.
    2. Use the Earlier Bot Message only as background.
    3. ONLY return a short noun phrase if the user's input is clearly connected to a topic in the conversation.
    4. If the user input does not refer to anything mentioned or suggested by the bot, return 'none'.
    5. Do NOT guess or assume a topic — only return what's clearly mentioned or referenced.
    6. Your response must be either:
       - a short noun phrase like "careers", "services", "technologies"
       - OR the word 'none'

    ---
    Earlier Bot Message: "{bot_msg_1}"
    Latest Bot Message (most important): "{bot_msg_2}"
    User Response (most important): "{user_input}"
    ---

    Main topic of interest:
    """

    try:
        response = call_mistral_model(prompt).strip().lower()
        return response
    except Exception as e:
        print(f"[ERROR] Failed to extract topic: {e}")
        return "none"

def handle_user_info_submission(user_input):
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
    
    return ' '.join(response)

def get_indeed_response(user_input, user=None, context_mode=False, response_meta=None):
    print("------------------------------------start------------------------------------------")
    response_meta = {'_from_kb': False, 'from_any_fun': False}

    if not user_input or not isinstance(user_input, str) or len(user_input.strip()) == 0:
        return "Please provide a valid input."
    
    WELCOME_RESPONSE = "Hello! Welcome to Indeed Inspiring Infotech. I'm your assistant here to help with all things about our company. How can I assist you today?"
    welcome_pattern = r"^(Hello\s[\w@.]+!|Hello tech enthusiast!)\sWelcome to Indeed Inspiring Infotech\. I'm your assistant here to help with all things about our company\. How can I assist you today\?$"

    if re.match(welcome_pattern, user_input.strip()):
        return WELCOME_RESPONSE

    history = load_session_history(history_file_path)

    print("[LANG_DEBUG] Starting language detection...")
    lang_variant = detect_language_variant(user_input, hinglish_words, minglish_words)
    script_type = detect_input_script(user_input)
    print(f"[LANG_DEBUG] Detected language variant: {lang_variant}, script type: {script_type}")
    translated_input = translate_to_english(user_input) if lang_variant not in ['en', 'hinglish', 'minglish'] else user_input
    print(f"[LANG_DEBUG] Translated input (if needed): {translated_input}")

    matched_url = get_website_guide_response(translated_input, "indeedinspiring.com")  
    has_url = matched_url and ("http://" in matched_url or "https://" in matched_url)

    response = None
    
    if not response and ("what is your name" in translated_input.lower() or "your name" in translated_input.lower()):
        print("[DEBUG] Response from: Name Handler")
        response = f"My name is {CHATBOT_NAME}. What would you like to know about Indeed Inspiring Infotech today?"

    if not response and history and not context_mode:
        follow_up_response = handle_follow_up_question(
            history, 
            translated_input, 
            user_input, 
            user,
            response_meta=response_meta
        )
        if follow_up_response:
            print("[DEBUG] Response from: Follow-up Handler")
            response = follow_up_response

    if not response:
        temp = handle_meta_questions(translated_input)
        if temp:
            print("[DEBUG] Response from: Meta Question Handler")
            response = temp
            response_meta['from_any_fun'] = True

    if not response:
        temp = handle_time_based_greeting(translated_input)
        if temp:
            print("[DEBUG] Response from: Time-Based Greeting")
            response = temp
            response_meta['from_any_fun'] = True

    if not response:
        temp = handle_date_related_queries(translated_input)
        if temp:
            print("[DEBUG] Response from: Date Handler")
            response = temp
            response_meta['from_any_fun'] = True

    if not response:
        temp = search_intents_and_respond(translated_input, indeed_kb)
        print("Knb_path:", content_path)
        if temp:
            print("[DEBUG] Response from: Knowledge Base (search_intents_and_respond)")
            response = temp
            response_meta['_from_kb'] = True

    if not response:
        temp = generate_nlp_response(translated_input)
        if temp:
            print("[DEBUG] Response from: NLP Generator")
            response = temp
            response_meta['from_any_fun'] = True

    if not response:
        temp = get_mistral_indeed_response(translated_input, history)
        if temp:
            print("[DEBUG] Response from: Mistral API")
            response = temp
            response_meta['from_any_fun'] = True

    if not response:
        response = "I couldn't find specific information about that. Could you rephrase your question or ask about something else?"

    if is_farewell(translated_input):
        print("[DEBUG] Detected farewell. Clearing session history.")
        save_session_history(history_file_path, [])

    final_response = update_and_respond_with_history(
        user_input,
        response,
        user=user,
        chatbot_type='indeed',
        context_mode=context_mode,
        response_meta=response_meta
    )

    lang_map = {
            'hinglish': 'hinglish',
            'minglish': 'minglish',
            'hi': 'hi',
            'mr': 'mr',
            'en': 'en'
        }
    
    final_response = translate_response(final_response, 'en', script_type)
    print("[FINAL DEBUG] Final response:", response)

    print("------------------------------------end------------------------------------------")
    return final_response