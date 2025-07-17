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



import re

import os
import re

def load_qa_pairs_from_file(relative_path):
    """
    Load Q&A pairs from a text file.
    Each question is expected to be in bold using ** (e.g., **Question**) followed by its answer.
    """
    try:
        # Get absolute path relative to this script's location
        base_dir = os.path.dirname(__file__)
        file_path = os.path.join(base_dir, relative_path)

        print("[DEBUG] Loading Q&A from:", file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Match bold question (**...**) followed by answer text
        qa_pairs = re.findall(r"\*\*(.*?)\*\*\s*([\s\S]*?)(?=\n\*\*|$)", content)

        formatted_pairs = [(q.strip(), a.strip()) for q, a in qa_pairs]
        print(f"[DEBUG] Loaded {len(formatted_pairs)} Q&A pairs")
        return formatted_pairs

    except Exception as e:
        print("[ERROR] Failed to load Q&A pairs:", str(e))
        return []

def format_qa_for_prompt(pairs):
    """
    Format the list of Q&A pairs into a string suitable for the Mistral model prompt.
    """
    return "\n".join([f"Q: {q}\nA: {a}" for q, a in pairs])


# def get_mistral_gmtt_response(user_query, history):
#     try:
#         if is_contact_request(user_query):
#             return (f"Please share your query/feedback/message with me and I'll "
#                    f"forward it to our team at {CONTACT_EMAIL}. "
#                    "Could you please tell me your name and email address?")

#         if is_info_request(user_query):
#             return ("Thank you for sharing your details! I've noted your "
#                    f"information and will share it with our team at {CONTACT_EMAIL}. "
#                    "Is there anything specific you'd like us to know?")
        
#         # Match content for context
#         match = find_matching_content(user_query, GMTT_INDEX, threshold=0.6)

#         # Debug print
#         if match:
#             print("\n[DEBUG] Matched Page Info:")
#             print(f"Title: {match['title']}")
#             print(f"URL: {match['url']}")
#             print(f"Content Preview:\n{match['text'][:500]}")
#         else:
#             print("[DEBUG] No matching content found from website index.\n")
        
#         relevant_text = match['text'][:500] if match else ""
#         prompt = f"""
# You are an AI assistant created exclusively for **Give Me Trees Foundation**. You are not a general-purpose assistant and must **strictly obey** the rules below without exceptions.

# ### STRICT RULES:
# 1. If the user's query is about GMTT and **matching content is found**, respond **only using that content**.
# 2. If the query is about GMTT but **no relevant content** is found in the crawled data, reply:  
#    "I couldn't find any official information related to that topic on our website, so I won't answer inaccurately."
# 3. If the query is a **greeting** or **casual conversation** (e.g., "hi", "how are you", "good morning"), respond smartly and politely.
# 4. If the query is **not clearly related to GMTT**, or if it includes **personal, hypothetical, or generic questions**, do **not** respond. Strictly reply with:  
#    "I specialize in Give Me Trees Foundation. I can't help with that."
# 5. Only return a valid URL of givemetrees.org if the user asks for a website link or guide.

# ⚠️ Do **NOT** attempt to answer anything outside the organization's scope, even if partially related or if the user insists. Avoid speculation, guessing, or fabricated answers.

# ### ORGANIZATION INFO:
# - Name: Give Me Trees Foundation
# - Founded: 1978 by Swami Prem Parivartan (Peepal Baba)
# - Focus: Environmental conservation through tree plantation
# - Website: https://www.givemetrees.org

# {f"- Relevant Matched Content:\n{relevant_text}" if relevant_text else ""}

# ### USER QUERY:
# {user_query}

# Respond based strictly on the above rules. Keep responses short, factual, and organization-specific.
# """

#         response = call_mistral_model(prompt)
        
#         # Inline response cleaning
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
#         driver = get_conversation_driver(history, 'mid')
#         return f"I'd be happy to tell you more. {driver}"

def get_mistral_gmtt_response(user_query, history):
    try:
        # Step 1: Check if it’s a contact/info request
        print("helo")
        if is_contact_request(user_query):
            return (f"Please share your query/feedback/message with me and I'll "
                    f"forward it to our team at {CONTACT_EMAIL}. "
                    "Could you please tell me your name and email address?")

        if is_info_request(user_query):
            return ("Thank you for sharing your details! I've noted your "
                    f"information and will share it with our team at {CONTACT_EMAIL}. "
                    "Is there anything specific you'd like us to know?")

        # Step 2: Try website-based content match
        match = find_matching_content(user_query, GMTT_INDEX, threshold=0.6)
        if match:
            relevant_text = match['text'][:500]
        else:
            relevant_text = ""

        # Step 3: Load Q&A from file and format it
        qa_pairs = load_qa_pairs_from_file('json_files/GMTT_Follow-up_questions.txt')
        qa_prompt = format_qa_for_prompt(qa_pairs)
    
        # Step 4: Build the prompt
        prompt = f"""
You are an AI assistant created for **Give Me Trees Foundation**. You must follow the strict rules below.

### STRICT RULES:
1. If the query matches any Q&A from the provided list, respond with the answer.
2. If the user query relates to GMTT but no match is found, say:  
   "I couldn't find any official information related to that topic on our website or files, so I won't answer inaccurately."
3. If the query is a greeting or casual talk (e.g., "hi", "how are you"), respond politely.
4. If it's not clearly related to GMTT, reply:  
   "I specialize in Give Me Trees Foundation. I can't help with that."

### Website Content (if any):
{relevant_text if relevant_text else '[No relevant content found]'}

### Known Q&A from Foundation Files:
{qa_prompt}

### User Query:
{user_query}

Respond only using the above information. Do not fabricate or guess. Keep it short, factual, and aligned with the organization's official content.
"""

        # Step 5: Call the model
        response = call_mistral_model(prompt)

        # Step 6: Clean output
        cleaned_response = response.split('[/handling_instruction]')[-1]
        cleaned_response = cleaned_response.split('Response template:')[0]
        cleaned_response = re.sub(r'\[.*?\]', '', cleaned_response)
        cleaned_response = re.sub(r'(Answer:|Follow-up question:)', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = ' '.join(cleaned_response.split())

        if len(cleaned_response) > 0:
            cleaned_response = cleaned_response[0].upper() + cleaned_response[1:]

        follow_up = get_conversation_driver(history, 'mid')
        # print("conversation_driver_after_in_update", type(history))
        final_response = f"{cleaned_response.strip()} {follow_up}"

        return final_response

    except Exception as e:
        import traceback
        print("[ERROR] Exception caught in get_mistral_gmtt_response")
        print("Error:", str(e))
        traceback.print_exc()
        print("conversion_driver_called_from_get_mistral_gmtt",type(history))
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

    # Get last 2 bot messages for contextual follow-up check
    bot_msg_1 = history[-2]["bot"] if len(history) >= 2 else ""
    bot_msg_2 = history[-1]["bot"] if len(history) >= 1 else ""

    # Check if user input is a contextual follow-up
    if not is_mistral_contextual_follow_up(bot_msg_1, bot_msg_2, user_input):
        driver = get_conversation_driver(history, 'intro' if len(history) < 2 else 'mid')
        current_response += f" {driver}"

    # Prevent repeated responses for repeated questions
    if any(h['user'].lower() == user_input.lower() for h in history[-3:]):
        current_response = f"Returning to your question, {current_response.lower()}"

    # Update history in required format
    history.append({
        "user": user_input.strip(),
        "bot": current_response.strip()
    })

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
            response = call_mistral_model(prompt, max_tokens=100)
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
    
 #------- Follow-up Question Handling ------- 
import re

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
        print("[DEBUG] Mistral Response:", response)

        if "CONTEXTUAL_FOLLOW_UP" in response:
            return True
        elif "NOT_CONTEXTUAL" in response:
            return False
        else:
            return False  # Fallback for unexpected outputs
    except Exception as e:
        print(f"[ERROR] Failed to evaluate contextual follow-up: {e}")
        return False

import re
def handle_follow_up_question(history, translated_input, user_input, user):
    """Handle follow-up questions by checking contextual relevance and providing a detailed response."""

    # Get last two bot messages and latest user input
    last_bot_msg = history[-1].get("bot", "")
    previous_bot_msg = history[-2]["bot"] if len(history) >= 2 else ""
    previous_user_msg = history[-2]["user"] if len(history) >= 2 else ""

    # Check if user input is a contextual follow-up
    if not is_mistral_contextual_follow_up(previous_bot_msg, last_bot_msg, user_input):
        return None

    print("[DEBUG] Detected contextual follow-up from user")

    # Extract topic of interest based on last two bot messages + user input
    topic = extract_topic_of_interest(previous_bot_msg, last_bot_msg, user_input)
    print(f"[DEBUG] Extracted topic: {topic}")

    # Find matching context for the topic
    match = find_matching_content(topic, GMTT_INDEX)
    matched_context =match.get("text", "")[:500] if match else ""

    print("topic:", topic)
    print("matched_context:", matched_context)
    # Generate detailed response using updated Mistral-based function
    # print("type(history) in handle_follow_up_question:", type(history))
    response = get_mistral_gmtt_response(topic, history)

    print("[DEBUG] Generated response handle_follow_up:", response)

    # Update history and respond
    return response

# Helper functions


def extract_topic_of_interest(bot_msg_1, bot_msg_2, user_input):
    """
    Extract the main topic the user is interested in based on the last two bot messages and the user input.
    Returns a short noun phrase like: 'tree plantation', 'volunteering', 'donation process'.
    """
    prompt = f"""
    From the conversation below, identify the single main topic the user is interested in.
    
    Consider:
    - Bot messages might introduce or suggest a topic.
    - The user input may explicitly or implicitly refer to one of them.
    - Return a short noun phrase only — no explanation.

    ---
    Bot Message 1 (Earlier): "{bot_msg_1}"
    Bot Message 2 (Latest): "{bot_msg_2}"
    User Response: "{user_input}"
    ---

    What is the main topic of interest?
    Reply with a clear, short noun phrase only (e.g., "volunteering opportunities", "how to donate").
    """

    try:
        response = call_mistral_model(prompt).strip()
        return response
    except Exception as e:
        print(f"[ERROR] Failed to extract topic: {e}")
        return "general information"


def generate_detailed_response(topic, context):
    """Generate a detailed response about the topic."""
    prompt = f"""
    As an assistant for Give Me Trees Foundation, explain the topic: "{topic}" in 2–3 short points.
    Use a professional, friendly tone. End with a related follow-up question.

    Context:
    {context}
    """
    return call_mistral_model(prompt).strip()

#-------follow up end-------   

'''main function to get response from gmtt bot'''

# def get_gmtt_response(user_input, user=None):
#     print("------------------------------------start------------------------------------------")
#     # Input validation
#     if not user_input or not isinstance(user_input, str) or len(user_input.strip()) == 0:
#         return "Please provide a valid input."

#     # Load conversation history
#     history = load_session_history(history_file_path)
    
#     # Check for name submission in previous message
#     if history and "please tell me your name" in history[-1]["bot"].lower():
#         print("[DEBUG] Response from: handle_user_info_submission")
#         return handle_user_info_submission(user_input)
    
#     # Language processing
#     input_lang = detect_language(user_input)
#     script_type = detect_input_language_type(user_input)
#     translated_input = translate_to_english(user_input) if input_lang != "en" else user_input

#     # URL matching (moved up since this is a quick check)
#     matched_url = get_website_guide_response(translated_input, "givemetrees.org")
#     has_url = matched_url and ("http://" in matched_url or "https://" in matched_url)

#     # Response generation pipeline - ordered by priority
#     response = None
    
#     # 1. Check for name query (should come before other handlers)
#     if not response and ("what is your name" in translated_input.lower() or "your name" in translated_input.lower()):
#         print("[DEBUG] Response from: Name Handler")
#         response = f"My name is {CHATBOT_NAME}. What would you like to know about Give Me Trees Foundation today?"
    
#     # 2. Handle follow-up questions (should come early as it may override other responses)
#     if not response and history:
#         follow_up_response = handle_follow_up_question(history, translated_input, user_input, user)
#         if follow_up_response:
#             print("[DEBUG] Response from: Follow-up Handler")
#             response = follow_up_response
    
#     # 3. Check meta questions
#     if not response:
#         temp = handle_meta_questions(translated_input)
#         if temp:
#             print("[DEBUG] Response from: Meta Question Handler")
#             response = temp
    
#     # 4. Check time-based greetings
#     if not response:
#         temp = handle_time_based_greeting(translated_input)
#         if temp:
#             print("[DEBUG] Response from: Time-Based Greeting")
#             response = temp
    
#     # 5. Check date-related queries
#     if not response:
#         temp = handle_date_related_queries(translated_input)
#         if temp:
#             print("[DEBUG] Response from: Date Handler")
#             response = temp
    
#     # 6. Check knowledge base (intents) - moved before NLP as it's more specific
#     if not response:
#         temp = search_intents_and_respond(translated_input, gmtt_kb)
#         if temp:
#             print("[DEBUG] Response from: Knowledge Base (search_intents_and_respond)")
#             response = temp
    
#     # 7. Generate NLP response
#     if not response:
#         temp = generate_nlp_response(translated_input)
#         if temp:
#             print("[DEBUG] Response from: NLP Generator")
#             response = temp
    
#     # 8. Fallback to Mistral API
#     if not response:
#         temp = get_mistral_gmtt_response(translated_input, history)
#         if temp:
#             print("[DEBUG] Response from: Mistral API")
#             response = temp
    
#     # Append URL if found but not included in response
#     if has_url and response and not re.search(r'https?://\S+', response):
#         print("[DEBUG] Appending URL to response")
#         response = f"{response}\n\nYou can find more details here: {matched_url}"

#     # Final fallback if nothing matched
#     if not response:
#         response = "I couldn't find specific information about that. Could you rephrase your question or ask about something else?"

#     # Handle farewell and clear history
#     if is_farewell(translated_input):
#         print("[DEBUG] Detected farewell. Clearing session history.")
#         save_session_history(history_file_path, [])  # Clear session history

#     # Enhance and return response
#     final_response = update_and_respond_with_history(
#         user_input, 
#         response, 
#         user=user, 
#         chatbot_type='gmtt'
#     )
    
    
#     # Add conversation driver if needed
#     if len(history) > 3 and not final_response.strip().endswith('?'):
#         follow_up = get_conversation_driver(history, 'mid')
#         final_response = f"{final_response} {follow_up}"

    
#     print("------------------------------------end------------------------------------------")
#     return final_response


'''main function to handle user contact information submission'''


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





def get_gmtt_response(user_input, user=None):
    print("------------------------------------start------------------------------------------")

    # -------------------- 1. Input validation --------------------
    if not user_input or not isinstance(user_input, str) or len(user_input.strip()) == 0:
        return "Please provide a valid input."

    # -------------------- 2. Load conversation history --------------------
    history = load_session_history(history_file_path)

    # print("DEBUG FINAL history type:", type(history))
    # print("DEBUG FINAL history[-1]:", history[-1])
    # print("DEBUG FINAL type(history[-1]):", type(history[-1]))


    # If last bot message asked for user's name, handle it as a name submission
    if history and "please tell me your name" in history[-1]["bot"].lower():
        print("[DEBUG] Response from: handle_user_info_submission")
        return handle_user_info_submission(user_input)

    # -------------------- 3. Language processing --------------------
    input_lang = detect_language(user_input)                           
    script_type = detect_input_language_type(user_input)             
    translated_input = translate_to_english(user_input) if input_lang != "en" else user_input 
    # -------------------- 4. URL intent matching --------------------
    matched_url = get_website_guide_response(translated_input, "givemetrees.org")  
    has_url = matched_url and ("http://" in matched_url or "https://" in matched_url)

    # -------------------- 5. Response generation pipeline --------------------
    response = None
    from_kb = False  

    # --- 5.1 Handle "what is your name?" type queries ---
    if not response and ("what is your name" in translated_input.lower() or "your name" in translated_input.lower()):
        print("[DEBUG] Response from: Name Handler")
        response = f"My name is {CHATBOT_NAME}. What would you like to know about Give Me Trees Foundation today?"

    # --- 5.2 Handle follow-up questions from previous conversation ---
    if not response and history:
        follow_up_response = handle_follow_up_question(history, translated_input, user_input, user)
        if follow_up_response:
            print("[DEBUG] Response from: Follow-up Handler")
            response = follow_up_response

    # --- 5.3 Handle meta questions like "who made you?" or "are you a bot?" ---
    if not response:
        temp = handle_meta_questions(translated_input)
        if temp:
            print("[DEBUG] Response from: Meta Question Handler")
            response = temp

    # --- 5.4 Handle greetings based on time (e.g., good morning) ---
    if not response:
        temp = handle_time_based_greeting(translated_input)
        if temp:
            print("[DEBUG] Response from: Time-Based Greeting")
            response = temp

    # --- 5.5 Handle date-specific queries like "What is today’s date?" ---
    if not response:
        temp = handle_date_related_queries(translated_input)
        if temp:
            print("[DEBUG] Response from: Date Handler")
            response = temp

    # --- 5.6 Search intent-based knowledge base for exact matching answers ---
    if not response:
        temp = search_intents_and_respond(translated_input, gmtt_kb)
        if temp:
            print("[DEBUG] Response from: Knowledge Base (search_intents_and_respond)")
            response = temp
            from_kb = True  # ✅ Mark that response is from the knowledge base

    # --- 5.7 Fallback to NLP generator for open-ended inputs ---
    if not response:
        temp = generate_nlp_response(translated_input)
        if temp:
            print("[DEBUG] Response from: NLP Generator")
            response = temp

    # --- 5.8 Final fallback: use Mistral API for general/ambiguous input ---
    if not response:
        # print("get_mistral_gmtt_response called with translated_input:", type(history))
        temp = get_mistral_gmtt_response(translated_input, history)
        if temp:
            print("[DEBUG] Response from: Mistral API")
            response = temp

    # -------------------- 6. Append URL if detected but not included in response --------------------
    if has_url and response and not re.search(r'https?://\S+', response):
        print("[DEBUG] Appending URL to response")
        response = f"{response}\n\nYou can find more details here: {matched_url}"

    # -------------------- 7. Final fallback if nothing worked --------------------
    if not response:
        response = "I couldn't find specific information about that. Could you rephrase your question or ask about something else?"

    # -------------------- 8. Handle user farewell and reset session --------------------
    if is_farewell(translated_input):
        print("[DEBUG] Detected farewell. Clearing session history.")
        save_session_history(history_file_path, [])  # Clear conversation history

    # -------------------- 9. Update history and prepare final response --------------------
    # print("[DEBUG] History:", type(history))
    final_response = update_and_respond_with_history(
        user_input,
        response,

        user=user,
        chatbot_type='gmtt'
    )
    print("from_kb_or_not",from_kb)
   
    # -------------------- 10. Add conversation driver (follow-up) if appropriate --------------------
    # ✅ Skip follow-up if the response came from the knowledge base
    if len(history) > 3 and not final_response.strip().endswith('?') and not from_kb:
        # print("[DEBUG] Adding conversation driver follow-up before_get_gmtt_response",type(history))
        follow_up = get_conversation_driver(history, 'mid')
        # print("conversation_driver_after_in_update", type(history))
        final_response = f"{final_response} {follow_up}"

    print("------------------------------------end------------------------------------------")
    return final_response
