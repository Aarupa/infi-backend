from .common_utils import *
import google.generativeai as genai  # type: ignore
from urllib.parse import urljoin
from .website_scraper import build_website_guide
from .website_guide import get_website_guide_response
import os
import json
# Gemini API configuration
genai.configure(api_key="AIzaSyAHosQnBRKJtmGJKACrTtLnN9U8XWKL8Go")

CHATBOT_NAME = "Infi"
GMTT_INDEX = {}

# Build absolute paths to JSON files
current_dir = os.path.dirname(__file__)
json_dir = os.path.join(current_dir, "json_files")

greetings_path = os.path.join(json_dir, "greetings.json")
farewells_path = os.path.join(json_dir, "farewells.json")
general_path = os.path.join(json_dir, "general.json")
content_path = os.path.join(json_dir, "trees.json")
history_file_path = os.path.join(json_dir, "session_history.json")

# Ensure history file exists
if not os.path.exists(history_file_path):
    with open(history_file_path, "w") as f:
        json.dump([], f)

# Load knowledge bases
greetings_kb = load_json_data(greetings_path).get("greetings", {})
farewells_kb = load_json_data(farewells_path).get("farewells", {})
general_kb = load_json_data(general_path).get("general", {})
gmtt_kb = load_knowledge_base(content_path)

# Language mapping for translation
LANGUAGE_MAPPING = {
    'mr': 'marathi',
    'hi': 'hindi',
    'en': 'english'
    
}

# Crawl website initially
def crawl_gmtt_website():
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

def get_gemini_gmtt_response(user_query):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
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
2. also handle general greetings and farewells and general conversations like hi, hello, how are you, etc.
3. For unrelated topics, reply that you don’t have info on that and focus only on Give Me Trees Foundation. Include the topic name in your response. Rephrase each time.
4. Keep responses concise (1 sentence maximum)
5. if needed mention to visit givemetrees.org for more details

Context: {context}

User Query: {user_query}

Response:"""

        response = model.generate_content(prompt)
        return response.text if response.text else "I couldn't generate a response. Please try again or visit givemetrees.org for more information."

    except Exception as e:
        print(f"[ERROR] Gemini call failed: {e}")
        return "I'm having trouble accessing organization information right now. Please visit givemetrees.org for details."

def update_and_respond_with_history(user_input, current_response):
    exit_keywords = ["bye", "bye bye", "exit"]
    history = load_session_history(history_file_path)

    if any(kw in user_input.lower() for kw in exit_keywords):
        open(history_file_path, "w").close()
        return current_response

    history_text = ""
    for turn in history:
        history_text += f"User: {turn['user']}\nBot: {turn['bot']}\n"

    prompt = f"""
        You are a smart assistant representing Give Me Trees Foundation.
        Using the conversation history below and the current system reply, generate a concise, coherent response that may incorporate context from history if relevant.

        Rules:
        - If the user has asked a similar or identical question earlier in Conversation History below then, start your reply with a phrase not exact but similar to \"As I mentioned earlier,\" and rephrase and slightly expand the original response.
        - Ensure the response is natural, contextual, and varies in tone. Avoid sounding repetitive or robotic.

        Conversation History:
        {history_text}

        Current System Response:
        {current_response}

        Final Answer (Keep it natural, relevant, and concise. Vary length based on question complexity):
        """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        final_response = model.generate_content(prompt)
        history.append({"user": user_input, "bot": final_response.text.strip()})
        save_session_history(history_file_path, history)
        return final_response.text.strip()
    except Exception:
        history.append({"user": user_input, "bot": current_response})
        save_session_history(history_file_path, history)
        return current_response

def get_gmtt_response(user_input):
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
        return update_and_respond_with_history(user_input, response)

    if response := handle_time_based_greeting(user_input):
        print("[INFO] Response from: Time-Based Greeting")
        return update_and_respond_with_history(user_input, response)

    if response := handle_date_related_queries(user_input):
        print("[INFO] Response from: Date Handler")
        return update_and_respond_with_history(user_input, response)

    if response := generate_nlp_response(user_input):
        print("[INFO] Response from: NLP Generator")
        return update_and_respond_with_history(user_input, response)

    print("[INFO] Response from: Gemini API")
    response = get_gemini_gmtt_response(user_input)
    return update_and_respond_with_history(user_input, response)

    return final_response
