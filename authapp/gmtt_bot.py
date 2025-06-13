from .common_utils import *
import google.generativeai as genai
from urllib.parse import urljoin
from .website_scraper import build_website_guide
from .website_guide import get_website_guide_response
import os
from deep_translator import GoogleTranslator
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate
from langdetect import detect, LangDetectException
import language_tool_python  # Optional (grammar correction)

# Gemini API configuration
genai.configure(api_key="AIzaSyCUG8Nkvc2fqpdJoa-3TZpyhLozd56JS80")

GMTT_NAME = "Infi"
GMTT_INDEX = {}

# Language mapping for translation (same as Indeed)
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

# Load knowledge bases (existing GMTT code)
current_dir = os.path.dirname(__file__)
json_dir = os.path.join(current_dir, "json_files")
greetings_path = os.path.join(json_dir, "greetings.json")
farewells_path = os.path.join(json_dir, "farewells.json")
general_path = os.path.join(json_dir, "general.json")
trees_path = os.path.join(json_dir, "trees.json")

greetings_kb = load_json_data(greetings_path).get("greetings", {})
farewells_kb = load_json_data(farewells_path).get("farewells", {})
general_kb = load_json_data(general_path).get("general", {})
gmtt_kb = load_knowledge_base(trees_path)

# Crawl GMTT website (existing)
def crawl_gmtt_website():
    global GMTT_INDEX
    GMTT_INDEX = crawl_website("https://www.givemetrees.org", max_pages=30)
    print(f"[INFO] Crawled {len(GMTT_INDEX)} pages from givemetrees.org")
    return GMTT_INDEX

GMTT_INDEX = crawl_gmtt_website()

# New: Detect if input is in English script (Romanized) or native script
def detect_input_script_type(text):
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return 'english_script' if (ascii_chars / len(text)) > 0.7 else 'native_script'

# New: Detect language (improved with fallback)
def detect_language(text):
    try:
        detected = detect(text)
        return detected if detected in LANGUAGE_MAPPING else 'en'
    except LangDetectException:
        return 'en'

# New: Translate to English (if needed)
def translate_to_english(text):
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except Exception as e:
        print(f"[ERROR] Translation failed: {e}")
        return text

# New: Translate response back to user's language & script
def translate_response(response_text, target_lang, input_script_type):
    if target_lang == 'en':
        return response_text
    
    try:
        # First translate to target language
        translated = GoogleTranslator(source='en', target=target_lang).translate(response_text)
        
        # If input was in English script, transliterate back
        if input_script_type == 'english_script' and target_lang in ['hi', 'mr', 'pa', 'ta', 'te', 'kn', 'gu', 'bn']:
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

# Updated: get_gemini_gmtt_response (now supports multilingual)
def get_gemini_gmtt_response(user_query):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        match = find_matching_content(user_query, GMTT_INDEX, threshold=0.6)

        context = """
        Give Me Trees Foundation is a non-profit organization dedicated to environmental conservation.
        Key Information:
        - Founded in 1978 by Kuldeep Bharti
        - Headquarters in New Delhi, India
        - Planted over 20 million trees
        - Focus areas: Urban greening, rural afforestation, environmental education
        - Website: https://www.givemetrees.org
        """

        if match:
            context += f"\n\nRelevant page content from {match['title']}:\n{match['text']}"

        prompt = f"""You are an assistant for Give Me Trees Foundation.
Rules:
1. Provide information only about Give Me Trees Foundation.
2. Handle greetings, farewells, and general conversations.
3. Keep responses concise (1-2 sentences).
4. If unsure, suggest visiting givemetrees.org.

Context: {context}

Query: {user_query}

Response:"""
        
        response = model.generate_content(prompt)
        return response.text if response.text else "Please visit givemetrees.org for more details."

    except Exception as e:
        print(f"[ERROR] Gemini API error: {e}")
        return "I'm having trouble accessing tree information. Visit givemetrees.org."

# Updated: Main get_gmtt_response (now multilingual)
def get_gmtt_response(user_input):
    if not user_input or not isinstance(user_input, str):
        return "Please enter a valid query."

    # Step 1: Detect language & script type
    input_lang = detect_language(user_input)
    script_type = detect_input_script_type(user_input)
    print(f"[DEBUG] Detected language: {input_lang}, Script: {script_type}")

    # Step 2: Translate to English (if needed)
    translated_input = translate_to_english(user_input) if input_lang != 'en' else user_input
    print(f"[DEBUG] Translated input: {translated_input}")

    # Step 3: Process query (existing GMTT logic)
    response = None

    if "what is your name" in translated_input.lower():
        print("[INFO] Response from: Name handler")
        response = f"My name is {GMTT_NAME}. I help with Give Me Trees queries."

    # if not response and (r := handle_greetings(translated_input, greetings_kb)):
    #     print("[INFO] Response from: Greetings handler")
    #     response = r

    # if not response and (r := handle_farewells(translated_input, farewells_kb)):
    #     print("[INFO] Response from: Farewells handler")
    #     response = r

    if not response and (r := search_knowledge(translated_input, gmtt_kb)):
        print("[INFO] Response from: Knowledge Base")
        response = r
    
    if not response and (r := handle_time_based_greeting(translated_input)):
        print("[INFO] Response from: Time-Based Greeting")
        response = r

    if not response and (r := handle_date_related_queries(translated_input)):
        print("[INFO] Response from: Date Handler")
        response = r

    if not response and (r := generate_nlp_response(translated_input)):
        print("[INFO] Response from: NLP model")
        response = r

    if not response:
        print("[INFO] No specific response found, using Gemini model")
        response = get_gemini_gmtt_response(translated_input)

    # Step 4: Translate response back to user's language & script
    final_response = translate_response(response, input_lang, script_type)
    print(f"[BOT] Final response: {final_response}")

    return final_response