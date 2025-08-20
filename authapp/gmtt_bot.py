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



def get_mistral_gmtt_response(user_query, history):
    try:
        if is_contact_request(user_query):
            return (f"Please share your query/feedback/message with me and I'll "
                   f"forward it to our team at {CONTACT_EMAIL}. "
                   "Could you please tell me your name and email address?")

        if is_info_request(user_query):
            return ("Thank you for sharing your details! I've noted your "
                   f"information and will share it with our team at {CONTACT_EMAIL}. "
                   "Is there anything specific you'd like us to know?")
        
        # Match content for context
        match = find_matching_content(user_query, GMTT_INDEX, threshold=0.6)

        # Debug print
        if match:
            print("\n[DEBUG] Matched Page Info:")
            print(f"Title: {match['title']}")
            print(f"URL: {match['url']}")
            print(f"Content Preview:\n{match['text'][:500]}")
        else:
            print("[DEBUG] No matching content found from website index.\n")
        
        relevant_text = match['text'][:500] if match else ""
        prompt = f"""
You are an AI assistant created exclusively for **Give Me Trees Foundation**. You are not a general-purpose assistant and must **strictly obey** the rules below without exceptions.

### STRICT RULES:
1. If the user's query is about GMTT and **matching content is found**, respond **only using that content**.
2. If the query is about GMTT but **no relevant content** is found in the crawled data, reply:  
   "I couldn't find any official information related to that topic on our website, so I won't answer inaccurately."
3. If the query is a **greeting** or **casual conversation** (e.g., "hi", "how are you", "good morning"), respond smartly and politely.
4. If the query is **not clearly related to GMTT**, or if it includes **personal, hypothetical, or generic questions**, do **not** respond. Strictly reply with:  
   "I specialize in Give Me Trees Foundation. I can't help with that."

⚠️ Do **NOT** attempt to answer anything outside the organization's scope, even if partially related or if the user insists. Avoid speculation, guessing, or fabricated answers.

### ORGANIZATION INFO:
- Name: Give Me Trees Foundation
- Founded: 1978 by Swami Prem Parivartan (Peepal Baba)
- Focus: Environmental conservation through tree plantation
- Website: https://www.givemetrees.org

{f"- Relevant Matched Content:\n{relevant_text}" if relevant_text else ""}

### USER QUERY:
{user_query}

Respond based strictly on the above rules. Keep responses short, factual, and organization-specific.
"""

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

def handle_meta_questions(user_input):
    """
    Handle meta-questions like 'what can I ask you' or 'how can you help me?'
    Returns a general assistant response if a match is found, focused on GMTT.
    """
    meta_phrases = [
        "what can i ask you", "suggest me some topics", "what topics can i ask",
        "how can you help", "what do you know", "what programs do you run",
        "what questions can i ask", "what information do you have",
        "what can you tell me", "what should i ask"
    ]
    
    lowered = user_input.lower()
    if any(phrase in lowered for phrase in meta_phrases):
        responses = [
            f"I'm here to help with all things related to Give Me Trees Foundation! "
            "You can ask me about our tree plantation initiatives, volunteer opportunities, "
            "environmental impact, or how to get involved.",
            
            "As a GMTT assistant, I can tell you about our conservation projects, "
            "Peepal tree initiatives, educational programs, and ways to support our cause. "
            "What would you like to know?",
            
            "Happy to help! You can ask about: "
            "- Our ongoing plantation drives\n"
            "- How to volunteer with us\n"
            "- The environmental impact of our work\n"
            "- Ways to donate or partner\n"
            "What interests you most?",
            
            "I specialize in information about Give Me Trees Foundation's environmental work. "
            "You might ask about:\n"
            "- Our founder Peepal Baba\n"
            "- Our methodology for tree care\n"
            "- Success stories from our projects\n"
            "- Upcoming events and campaigns",
            
            "Let me suggest some topics:\n"
            "• Our focus on Peepal trees and why they're special\n"
            "• How we ensure planted trees survive long-term\n"
            "• Stories from our volunteer community\n"
            "• Our educational programs in schools\n"
            "Which would you like to explore?"
        ]
        return random.choice(responses)
    return None

def update_and_respond_with_history(user_input, current_response, user=None, chatbot_type='gmtt'):
    history = load_session_history(history_file_path)
    
    # Add conversation driver if missing
    if not is_mistral_follow_up(current_response):
        driver = get_conversation_driver(history, 'intro' if len(history) < 2 else 'mid')
        current_response += f" {driver}"
    
    # Ensure varied responses for repeated questions
    if any(h['user'].lower() == user_input.lower() for h in history[-3:]):
        current_response = f"Returning to your question, {current_response.lower()}"
    
    history.append({"user": user_input, "bot": current_response})
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

def search_intents_and_respond(user_input, gmtt_kb):
    """
    Searches the knowledge base for relevant information.
    If found, generates a context-based response using the Mistral model.
    If not found, returns None to indicate fallback is needed.
    """
    block = search_knowledge_block(user_input, gmtt_kb)
    
    if block:
        context = format_kb_for_prompt(block)

        prompt = f"""You are a helpful assistant from Give Me Trees Foundation.

Answer the user's question using ONLY the given context. Speak as "we." Then:
1. Ask a related follow-up question but not mention followup word.

Context:
{context}

User Question: {user_input}

Give a helpful, friendly, and natural response.
"""

        try:
            response = call_mistral_model(prompt, max_tokens=90)
            response = re.sub(r'\[.*?\]', '', response).strip()

            # Add fallback suggestions if info is incomplete
            if "not provided" in response.lower() or "not available" in response.lower():
                related_topics = []
                if "plant" in user_input.lower():
                    related_topics = ["our plantation methods", "volunteer opportunities", "tree care tips"]
                elif "volunteer" in user_input.lower():
                    related_topics = ["upcoming events", "registration process", "impact of volunteering"]

                if related_topics:
                    response += f" However, we can also share about {', '.join(related_topics[:-1])} or {related_topics[-1]}."
                else:
                    response += " Would you like information about our projects, volunteering, or something else?"

            if not response.endswith(('.', '!', '?')):
                response += "."

            return response

        except Exception as e:
            print(f"[ERROR] Knowledge base search failed: {e}")
            return "We're having trouble processing your request right now. Could you please try again?"
    else:
        # No block found — caller should handle fallback
        return None
    
def get_gmtt_response(user_input, user=None):
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

    # Handle follow-up response continuation early
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
            response_affirmative = call_mistral_model(affirmative_check_prompt)
            match = re.search(r'\b(YES|NO)\b', response_affirmative.strip().upper())
            is_affirmative = match.group(1) if match else "NO"

            if is_affirmative == "YES":
                topic_prompt = f"""
                    What was the main topic being discussed before this follow-up question?
                    Previous Bot Message: "{history[-2]['bot'] if len(history) >= 2 else ''}"
                    Follow-up Question: "{last_bot_msg}"
                    Answer with a noun phrase (like: 'volunteer programs', 'tree plantation', etc.):
                    """
                topic = call_mistral_model(topic_prompt).strip()
                print(f"[DEBUG] Extracted topic: {topic}")

                topic_match = find_matching_content(topic, GMTT_INDEX)
                matched_context = topic_match['text'][:500] if topic_match else ""

                detail_prompt = f"""
                    As an assistant for Give Me Trees Foundation, explain the topic: "{topic}" in 2–3 short points.
                    Use a professional, friendly tone. End with a related follow-up question.

                    Context:
                    {matched_context}
                    """
                response = call_mistral_model(detail_prompt).strip()
                return update_and_respond_with_history(user_input, response, user=user)

    # NEW: Try to find relevant URL first for any query
    matched_url = get_website_guide_response(translated_input, "givemetrees.org")
    print("matched",matched_url)
    print("stop")
    has_url = matched_url and ("http://" in matched_url or "https://" in matched_url)
    # Response generation pipeline
    response = None
    
    # 1. Check for name query
    if not response and ("what is your name" in translated_input.lower() or "your name" in translated_input.lower()):
        print("[DEBUG] Response from: Name Handler")
        response = f"My name is {CHATBOT_NAME}. What would you like to know about Give Me Trees Foundation today?"
    

    # 3. Check meta questions
    if not response:
        temp = handle_meta_questions(translated_input)
        if temp:
            print("[DEBUG] Response from: Meta Question Handler")
            response = temp
    
    # 4. Check time-based greetings
    if not response:
        temp = handle_time_based_greeting(translated_input)
        if temp:
            print("[DEBUG] Response from: Time-Based Greeting")
            response = temp
    
    # 5. Check date-related queries
    if not response:
        temp = handle_date_related_queries(translated_input)
        if temp:
            print("[DEBUG] Response from: Date Handler")
            response = temp
    
    # 6. Generate NLP response
    if not response:
        temp = generate_nlp_response(translated_input)
        if temp:
            print("[DEBUG] Response from: NLP Generator")
            response = temp

    # 7. Check knowledge base (intents)
    if not response:
        temp = search_intents_and_respond(translated_input, gmtt_kb)
        if temp:
            print("[DEBUG] Response from: Knowledge Base (search_intents_and_respond)")
            response = temp
    
    # 8. Fallback to Mistral API
    if not response:
        temp = get_mistral_gmtt_response(translated_input, history)
        if temp:
            print("[DEBUG] Response from: Mistral API")
            response = temp
    
    # NEW: If we have a URL but it wasn't included in any response, append it
    if has_url and response and (matched_url not in response):
        print("[DEBUG] Appending URL to response")
        response = f"{response}\n\nYou can find more details here: {matched_url}"

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
        chatbot_type='gmtt'
    )
    
    # Ensure conversation keeps moving forward
    if len(history) > 3 and not final_response.strip().endswith('?'):
        follow_up = get_conversation_driver(history, 'mid')
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