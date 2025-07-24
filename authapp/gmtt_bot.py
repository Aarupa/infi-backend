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

def mistral_translate_response(response_text, target_lang_code):
    # Build appropriate prompt based on target
    if target_lang_code == 'hinglish':
        prompt = f"""Translate the following English text about tree conservation to clear and natural Hindi written in English letters (Hinglish).
            Follow these rules strictly:
            1. Keep it short (1-2 sentences max) and easy to understand
            2. Use common Hindi words with English environmental terms like "tree plantation", "sapling", "volunteer"
            3. Sound friendly and motivational like you're talking to a volunteer
            4. Never add explanations or notes about the translation
            5. Maintain the original meaning exactly

            Example Good Output:
            "Humare saath volunteer karke peepal ke ped lagayein - yeh environment ke liye sabse beneficial hai"

            Input Text to Translate:
            {response_text}

            Translated Hinglish Output:"""
    elif target_lang_code == 'minglish':
        prompt = f"""Translate the following English text about tree conservation to clear and natural Marathi written in English letters (Minglish).
            Follow these rules strictly:
            1. Keep it short (1-2 sentences max) and easy to understand
            2. Use common Marathi words with English environmental terms like "tree plantation", "sapling", "volunteer"
            3. Sound friendly and motivational like you're talking to a volunteer
            4. Never add explanations or notes about the translation
            5. Maintain the original meaning exactly

            Example Good Output:
            "Amhi saglyana bolato ki ped lagava, peepal cha ped environment sathi khup chhan ahe"

            Input Text to Translate:
            {response_text}

            Translated Minglish Output:"""

    else:
        return response_text  # No translation needed

    mistral_response = call_mistral_model(prompt, max_tokens=70).strip()
    
    # Step 0: If response starts with "Hindi Translation:", use only the part after that
    if mistral_response.lower().startswith("hindi translation:"):
        mistral_response = mistral_response[len("Hindi Translation:"):].strip()

    # Step 1: Try to extract text within double quotes
    match = re.search(r'"([^"]+)"', mistral_response)
    if match:
        cleaned = match.group(1).strip()
        if ':' in cleaned:
            cleaned = cleaned.split(':', 1)[1].strip()
    else:
        # Fallback: check for only starting quote
        partial_match = re.search(r'"([^"]+)', mistral_response)
        if partial_match:
            cleaned = partial_match.group(1).strip()
            if ':' in cleaned:
                cleaned = cleaned.split(':', 1)[1].strip()
        else:
            # Fallback: use entire mistral response
            cleaned = mistral_response.strip()

    # Step 3: Truncate to last period, unless it's part of 1. to 5.
    last_dot_index = cleaned.rfind('.')
    if last_dot_index != -1:
        # Check character before the dot
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

def crawl_gmtt_website():
    print("[DEBUG] crawl_gmtt_website() called")
    global GMTT_INDEX
    GMTT_INDEX = crawl_website("https://www.givemetrees.org", max_pages=100)
    print(f"[INFO] Crawled {len(GMTT_INDEX)} pages from givemetrees.org")
    return GMTT_INDEX

GMTT_INDEX = crawl_gmtt_website()




import os


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
        print("match", match)
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

        
        return cleaned_response.strip()

    except Exception as e:
        import traceback
        print("[ERROR] Exception caught in get_mistral_gmtt_response")
        print("Error:", str(e))
        traceback.print_exc()
        print("conversion_driver_called_from_get_mistral_gmtt")
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

# def update_and_respond_with_history(user_input, current_response, user=None, chatbot_type='gmtt'):
#     history = load_session_history(history_file_path)

#     # Get last 2 bot messages for contextual follow-up check
#     bot_msg_1 = history[-2]["bot"] if len(history) >= 2 else ""
#     bot_msg_2 = history[-1]["bot"] if len(history) >= 1 else ""

#     # Check if user input is a contextual follow-up
#     if not is_mistral_contextual_follow_up(bot_msg_1, bot_msg_2, user_input):
#         print("Get Conversation Driver called from update_and_respond_with_history")
#         driver = get_conversation_driver(history, 'intro' if len(history) < 2 else 'mid')
#         current_response += f" {driver}"

#     # Prevent repeated responses for repeated questions
#     if any(h['user'].lower() == user_input.lower() for h in history[-3:]):
#         current_response = f"Returning to your question, {current_response.lower()}"

#     # Update history in required format
#     history.append({
#         "user": user_input.strip(),
#         "bot": current_response.strip()
#     })

#     save_session_history(history_file_path, history)

#     return current_response

def update_and_respond_with_history(user_input, current_response, user=None, chatbot_type='gmtt', context_mode=False, response_meta=None):
    """
    Updates conversation history and modifies responses based on context.
    Handles all conversation driver logic and contextual adjustments.
    
    Args:
        user_input: Current user message
        current_response: Initial bot response (string)
        user: Optional user object
        chatbot_type: Type of chatbot (default 'gmtt')
        context_mode: Whether in context-sensitive mode
        response_meta: Dictionary containing response metadata
        
    Returns:
        Final response after all contextual processing
    """
    # Load conversation history
    history = load_session_history(history_file_path)
    
    # Get last 2 bot messages for context analysis
    bot_msg_1 = history[-2]["bot"] if len(history) >= 2 else ""
    bot_msg_2 = history[-1]["bot"] if len(history) >= 1 else ""
    
    # -------------------- Contextual Processing --------------------
    # 1. Check for contextual follow-up
    is_contextual = False #is_mistral_contextual_follow_up(bot_msg_1, bot_msg_2, user_input)
    
    # 2. Get response source flags (safe for strings)
    meta = response_meta or {}
    from_kb = meta.get('_from_kb', False)
    from_any_fun = meta.get('from_any_fun', False)
    print(f"[DEBUG] Contextual: {is_contextual}, From KB: {from_kb}, From Any Fun: {from_any_fun}")
    
    # -------------------- Response Modifications --------------------
    # 1. Handle duplicate questions
    if any(h['user'].lower() == user_input.lower() for h in history[-3:]):
        current_response = f"Returning to your question, {current_response.lower()}"
    
    # 2. Add conversation driver when appropriate
    should_add_driver = (
            not from_kb and
            from_any_fun
    )

    print(f"[DEBUG] Should add driver: {should_add_driver}")
    
    if should_add_driver:
        print("should_add_driver is True")
        driver_type = 'intro' if len(history) < 2 else 'mid'
        driver = get_conversation_driver(history, driver_type)
        current_response = f"{current_response} {driver}"
    
    # -------------------- History Management --------------------
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
        # print("[DEBUG] Mistral Response:", response)

        if "CONTEXTUAL_FOLLOW_UP" in response:
            return True
        elif "NOT_CONTEXTUAL" in response:
            return False
        else:
            return False  # Fallback for unexpected outputs
    except Exception as e:
        print(f"[ERROR] Failed to evaluate contextual follow-up: {e}")
        return False


def handle_follow_up_question(history, translated_input, user_input, user, response_meta=None):
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

    # If topic is empty or None, return None
    if not topic:
        print("[DEBUG] Topic not found.")
        return None

    print("topic:", topic)
    
    # Generate detailed response using updated Mistral-based function
    response = get_gmtt_response(topic, user=None, context_mode=True, response_meta=response_meta)


    # Update history and respond
    return response

# Helper functions


def extract_topic_of_interest(bot_msg_1, bot_msg_2, user_input):
    """
    Extract the main topic the user is referring to, with high priority on the latest bot message and user input.
    If the user input does not clearly refer to a topic from the recent conversation, return 'none'.
    """
    prompt = f"""
    Your task is to extract the main topic of interest from the following conversation.

    Rules:
    1. Focus mainly on the Latest Bot Message and the User Response.
    2. Use the Earlier Bot Message only as background.
    3. ONLY return a short noun phrase if the user's input is clearly connected to a topic in the conversation.
    4. If the user input does not refer to anything mentioned or suggested by the bot, return 'none'.
    5. Do NOT guess or assume a topic — only return what's clearly mentioned or referenced.
    6. Your response must be either:
       - a short noun phrase like "volunteering", "donation process", "tree plantation"
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



#-------follow up end-------   



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



def get_gmtt_response(user_input, user=None, context_mode=False, response_meta=None):

    print("------------------------------------start------------------------------------------")
    # Add at the start of the function
    response_meta = {'_from_kb': False, 'from_any_fun': False}

    # -------------------- 1. Input validation --------------------
    if not user_input or not isinstance(user_input, str) or len(user_input.strip()) == 0:
        return "Please provide a valid input."
    
    # -------------------- 2. Check for welcome pattern --------------------
    import re

    WELCOME_RESPONSE = "Hello! Welcome to Give Me Trees Foundation. I'm your eco-assistant here to help with all things trees and sustainability. How can I assist you today?"

    welcome_pattern = r"^(Hello\s[\w@.]+!|Hello tree lover!)\sWelcome to Give Me Trees Foundation\. I'm your eco-assistant here to help with all things trees and sustainability\. How can I assist you today\?$"

    if re.match(welcome_pattern, user_input.strip()):
        return WELCOME_RESPONSE


    # -------------------- 2. Load conversation history --------------------
    history = load_session_history(history_file_path)

    # print("DEBUG FINAL history type:", type(history))
    # print("DEBUG FINAL history[-1]:", history[-1])
    # print("DEBUG FINAL type(history[-1]):", type(history[-1]))


    # If last bot message asked for user's name, handle it as a name submission
    # if history and "please tell me your name" in history[-1]["bot"].lower():
    #     print("[DEBUG] Response from: handle_user_info_submission")
    #     return handle_user_info_submission(user_input)

    # -------------------- 3. Language processing --------------------
    print("[LANG_DEBUG] Starting language detection...")
    lang_variant = detect_language_variant(user_input, hinglish_words, minglish_words)
    script_type = detect_input_script(user_input)
    print(f"[LANG_DEBUG] Detected language variant: {lang_variant}, script type: {script_type}")
    translated_input = translate_to_english(user_input) if lang_variant not in ['en', 'hinglish', 'minglish'] else user_input
    print(f"[LANG_DEBUG] Translated input (if needed): {translated_input}")

    # -------------------- 4. URL intent matching --------------------
    matched_url = get_website_guide_response(translated_input, "givemetrees.org")  
    has_url = matched_url and ("http://" in matched_url or "https://" in matched_url)

    # -------------------- 5. Response generation pipeline --------------------
    response = None
    
    # --- 5.1 Handle "what is your name?" type queries ---
    if not response and ("what is your name" in translated_input.lower() or "your name" in translated_input.lower()):
        print("[DEBUG] Response from: Name Handler")
        response = f"My name is {CHATBOT_NAME}. What would you like to know about Give Me Trees Foundation today?"

    # --- 5.2 Handle follow-up questions from previous conversation ---
    if not response and history and not context_mode:
        follow_up_response = handle_follow_up_question(
            history, 
            translated_input, 
            user_input, 
            user,
            response_meta=response_meta  # Pass the existing metadata
        )
        if follow_up_response:
            print("[DEBUG] Response from: Follow-up Handler")
            response = follow_up_response

    # --- 5.3 Handle meta questions like "who made you?" or "are you a bot?" ---
    if not response:
        temp = handle_meta_questions(translated_input)
        if temp:
            print("[DEBUG] Response from: Meta Question Handler")
            response = temp
            response_meta['from_any_fun'] = True

    # --- 5.4 Handle greetings based on time (e.g., good morning) ---
    if not response:
        temp = handle_time_based_greeting(translated_input)
        if temp:
            print("[DEBUG] Response from: Time-Based Greeting")
            response = temp
            response_meta['from_any_fun'] = True

    # --- 5.5 Handle date-specific queries like "What is today’s date?" ---
    if not response:
        temp = handle_date_related_queries(translated_input)
        if temp:
            print("[DEBUG] Response from: Date Handler")
            response = temp
            response_meta['from_any_fun'] = True

    # --- 5.6 Search intent-based knowledge base for exact matching answers ---
    if not response:
        temp = search_intents_and_respond(translated_input, gmtt_kb)
        if temp:
            print("[DEBUG] Response from: Knowledge Base (search_intents_and_respond)")
            response = temp
            response_meta['_from_kb'] = True  # ✅ Mark that response is from the knowledge base

    # --- 5.7 Fallback to NLP generator for open-ended inputs ---
    if not response:
        temp = generate_nlp_response(translated_input)
        if temp:
            print("[DEBUG] Response from: NLP Generator")
            response = temp
            response_meta['from_any_fun'] = True

    # --- 5.8 Final fallback: use Mistral API for general/ambiguous input ---
    if not response:
        temp = get_mistral_gmtt_response(translated_input, history)
        if temp:
            print("[DEBUG] Response from: Mistral API")
            response = temp
            response_meta['from_any_fun'] = True
            

    # -------------------- 6. Append URL if detected but not included in response --------------------
    # if has_url and response and not re.search(r'https?://\S+', response):
    #     print("[DEBUG] Appending URL to response")
    #     response = f"{response}\n\nYou can find more details here: {matched_url}"

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
        chatbot_type='gmtt',
        context_mode=context_mode,  # <-- ADD THIS PARAMETER
        response_meta=response_meta
    )

    lang_map = {
            'hinglish': 'hinglish',
            'minglish': 'minglish',
            'hi': 'hi',
            'mr': 'mr',
            'en': 'en'
        }
    
    # target_lang = lang_map.get(lang_variant, 'en')
    # print(f"[LANG_DEBUG] Preparing to translate to: {target_lang}")

    # if target_lang == 'hinglish':
    #     final_response = mistral_translate_response(final_response, 'hinglish')
    # elif target_lang == 'minglish':
    #     final_response = mistral_translate_response(final_response, 'minglish')
    # # elif target_lang in ['hi', 'mr']:
    #     final_response = translate_response(final_response, target_lang, script_type)

    final_response = translate_response(final_response, 'en', script_type)

    # print("response from kb or not",from_kb)
    # -------------------- 10. Add conversation driver (follow-up) if appropriate --------------------
    # ✅ Skip follow-up if the response came from the knowledge base
    # if not context_mode and len(history) > 3 and not final_response.strip().endswith('?') and not from_kb and mis:
    #     print("get_conversation_driver() called from:get_gmtt_response")
    #     follow_up = get_conversation_driver(history, 'mid')
    #     # print("conversation_driver_after_in_update", type(history))
    #     final_response = f"{final_response} {follow_up}"

    print("------------------------------------end------------------------------------------")
    return final_response
