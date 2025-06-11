from .common_utils import *
import google.generativeai as genai  # type: ignore
from urllib.parse import urljoin
from .website_scraper import build_website_guide
from .website_guide import get_website_guide_response
import os
from deep_translator import GoogleTranslator
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate
from langdetect import detect, LangDetectException

# Gemini API configuration
genai.configure(api_key="AIzaSyA4bFTPKOQ3O4iKLmvQgys_ZjH_J1MnTUs")

CHATBOT_NAME = "Infi"
INDEED_INDEX = {}

# Build absolute paths to JSON files
current_dir = os.path.dirname(__file__)
json_dir = os.path.join(current_dir, "json_files")

greetings_path = os.path.join(json_dir, "greetings.json")
farewells_path = os.path.join(json_dir, "farewells.json")
general_path = os.path.join(json_dir, "general.json")
content_path = os.path.join(json_dir, "content.json")

# Load knowledge bases
greetings_kb = load_json_data(greetings_path).get("greetings", {})
farewells_kb = load_json_data(farewells_path).get("farewells", {})
general_kb = load_json_data(general_path).get("general", {})
indeed_kb = load_knowledge_base(content_path)

# Language mapping for translation
LANGUAGE_MAPPING = {
    'mr': 'marathi',
    'hi': 'hindi',
    'en': 'english',
    'es': 'spanish',
    'fr': 'french',
    'de': 'german',
    'ja': 'japanese',
    'ko': 'korean',
    'zh': 'chinese',
    'pa': 'punjabi',
    'ta': 'tamil',
    'te': 'telugu',
    'kn': 'kannada',
    'gu': 'gujarati',
    'bn': 'bengali'
}

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

def get_gemini_indeed_response(user_query):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        match = find_matching_content(user_query, INDEED_INDEX, threshold=0.6)

        best_match = None
        best_score = 0
        query_keywords = set(user_query.lower().split())

        for url, data in INDEED_INDEX.items():
            page_keywords = set(data['text'].lower().split())
            match_score = len(query_keywords & page_keywords)
            if match_score > best_score:
                best_match = data
                best_score = match_score

        context = """
        Indeed Inspiring Infotech is a technology company providing innovative IT solutions.
        Key Information:
        - Founded by Kushal Sharma in 2016
        - Specializes in AI, web development, and digital transformation
        - Website: https://indeedinspiring.com
        """

        if match:
            context += f"\n\nRelevant page content from {match['title']}:\n{match['text']}"
            print(f"[DEBUG] Matched page title: {match['title']}")
            print(f"[DEBUG] Matched page snippet:\n{match['text'][:500]}")

        prompt = f"""You are an assistant for Indeed Inspiring Infotech and developed by Indeed Inspiring AIML team.

Strict Rules:
1. Only provide information about Indeed Inspiring Infotech from the website indeedinspiring.com
2. Also handle general greetings, farewells, and conversations like hi, hello, how are you, etc.
3. For other topics, respond: \"I specialize in Indeed Inspiring Infotech related questions.\"
4. Keep responses concise (1 sentence maximum).
5. If needed, mention to visit indeedinspiring.com for more details.

Context: {context}

User Query: {user_query}

Response:"""

        response = model.generate_content(prompt)
        return response.text if response.text else "I couldn't generate a response. Please try again or visit indeedinspiring.com for more information."

    except Exception as e:
        print(f"[ERROR] Gemini call failed: {e}")
        return "I'm having trouble accessing company information right now. Please visit indeedinspiring.com for details."

grammar_tool = language_tool_python.LanguageTool('en-US')

def is_grammatically_correct(sentence):
    matches = grammar_tool.check(sentence)
    # If there are no grammar errors, return True
    return len(matches) == 0

def get_indeed_response(user_input):
    if not user_input or not isinstance(user_input, str) or len(user_input.strip()) == 0:
        return "Please provide a valid input."

    # Step 1: Detect input language and script type
    input_lang = detect_language(user_input)
    script_type = detect_input_language_type(user_input)
    print(f"[DEBUG] Input language detected: {input_lang}, Script type: {script_type}")

    # Step 2: Translate input to English if needed
    translated_input = translate_to_english(user_input) if input_lang != "en" else user_input
    if input_lang != "en":
        print(f"[DEBUG] Translated input to English: {translated_input}")

    # Step 3: Chatbot processing
    response = None

    if not response and ("what is your name" in translated_input.lower() or "your name" in translated_input.lower()):
        print("[INFO] Response from: Name handler")
        response = f"My name is {CHATBOT_NAME}. How can I assist you with Indeed Inspiring Infotech?"

    if not response and (r := search_knowledge(translated_input, indeed_kb)):
        print("[INFO] Response from: Knowledge Base")
        response = r

    if not response and (r := handle_time_based_greeting(translated_input)):
        print("[INFO] Response from: Time-Based Greeting")
        response = r

    if not response and (r := handle_date_related_queries(translated_input)):
        print("[INFO] Response from: Date Handler")
        response = r

    if not response and (r := generate_nlp_response(translated_input)):
        print("[INFO] Response from: NLP Fallback")
        response = r

    # Step 4: Fallback to Gemini if no other response was generated
    if not response:
        print("[INFO] Response from: Gemini Fallback")
        response = get_gemini_indeed_response(translated_input)
    
    if not response:
        website_response = get_website_guide_response(translated_input, "indeedinspiring.com", "https://indeedinspiring.com")
        if website_response:
            print("[INFO] Response from: Website Guide")
            response = f"I found this relevant page for you: {website_response}"
    # Ensure we have a response at this point
    if not response:
        response = "I couldn't understand your query. Please visit indeedinspiring.com for more information."

    # Step 5: Translate response back to input language if needed
    final_response = translate_response(response, input_lang, script_type)
    print(f"[BOT] Final response: {final_response}")

    return final_response