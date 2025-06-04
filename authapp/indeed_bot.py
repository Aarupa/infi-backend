from .common_utils import *
import google.generativeai as genai  # type: ignore
from urllib.parse import urljoin
import os
from deep_translator import GoogleTranslator
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate
import regex as re

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

# Language and script configuration
LANGUAGE_MAPPING = {
    'mr': {'name': 'marathi', 'script': 'devanagari'},
    'hi': {'name': 'hindi', 'script': 'devanagari'},
    'en': {'name': 'english', 'script': 'latin'},
    'es': {'name': 'spanish', 'script': 'latin'},
    'fr': {'name': 'french', 'script': 'latin'},
    # Add more languages as needed
}

# Common transliterations mapping for Indian languages
COMMON_TRANSLITERATIONS = {
    'mr': {
        'ahe': 'आहे', 'aahe': 'आहे', 'nav': 'नाव', 'naav': 'नाव',
        'kay': 'काय', 'kaay': 'काय', 'tuzhe': 'तुझे', 'tumche': 'तुमचे',
        'mazha': 'माझा', 'mi': 'मी', 'tu': 'तू', 'tumhi': 'तुम्ही'
    },
    'hi': {
        'hai': 'है', 'hain': 'हैं', 'naam': 'नाम', 'kyun': 'क्यों',
        'kya': 'क्या', 'tumhara': 'तुम्हारा', 'mera': 'मेरा',
        'aapka': 'आपका', 'main': 'मैं', 'tum': 'तुम', 'aap': 'आप'
    }
}

def is_latin_script(text):
    """Check if text is primarily in Latin script"""
    latin_chars = sum(1 for c in text if ord(c) < 128 and c.isalpha())
    return latin_chars / max(1, len(text)) > 0.7

def normalize_transliteration(text, lang_code):
    """Normalize common transliteration variations"""
    if lang_code not in COMMON_TRANSLITERATIONS:
        return text
    
    words = re.findall(r'\w+|\W+', text)
    normalized_words = []
    for word in words:
        lower_word = word.lower()
        if lower_word in COMMON_TRANSLITERATIONS[lang_code]:
            normalized_words.append(COMMON_TRANSLITERATIONS[lang_code][lower_word])
        else:
            normalized_words.append(word)
    return ''.join(normalized_words)

def transliterate_to_native(text, lang_code):
    """Convert English-script text to native script"""
    if lang_code not in ['hi', 'mr'] or not is_latin_script(text):
        return text
    
    try:
        # First normalize common transliterations
        normalized = normalize_transliteration(text, lang_code)
        
        # Then use proper transliteration
        if lang_code == 'hi':
            return transliterate(normalized, sanscript.ITRANS, sanscript.DEVANAGARI)
        elif lang_code == 'mr':
            return transliterate(normalized, sanscript.ITRANS, sanscript.DEVANAGARI)
        return text
    except Exception as e:
        print(f"[ERROR] Transliteration failed: {e}")
        return text

def transliterate_to_latin(text, lang_code):
    """Convert native script text to Latin/English script"""
    if lang_code not in ['hi', 'mr'] or is_latin_script(text):
        return text
    
    try:
        if lang_code == 'hi':
            return transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS)
        elif lang_code == 'mr':
            return transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS)
        return text
    except Exception as e:
        print(f"[ERROR] Transliteration failed: {e}")
        return text

def detect_language(text):
    """Enhanced language detection with transliteration awareness"""
    try:
        # First check if it's English script for Indian languages
        if is_latin_script(text):
            # Try to detect language from transliterated text
            detected = GoogleTranslator().detect(text[:500])  # Limit length for API
            if detected in ['hi', 'mr']:
                return detected
        # Regular detection for other cases
        return GoogleTranslator().detect(text)
    except Exception as e:
        print(f"[ERROR] Language detection failed: {e}")
        return 'en'

def translate_to_english(text, src_lang):
    """Translate to English with transliteration handling"""
    try:
        if src_lang == 'en':
            return text
        
        # If input is in Latin script for Indian language, first convert to native
        if src_lang in ['hi', 'mr'] and is_latin_script(text):
            native_text = transliterate_to_native(text, src_lang)
            return GoogleTranslator(source=src_lang, target='en').translate(native_text)
        
        return GoogleTranslator(source=src_lang, target='en').translate(text)
    except Exception as e:
        print(f"[ERROR] Translation to English failed: {e}")
        return text

def translate_response(response_text, target_lang, input_text):
    """Translate response matching the input script style"""
    try:
        if target_lang == 'en':
            return response_text
        
        # Determine if input was in Latin script
        input_in_latin = is_latin_script(input_text)
        
        # First translate to target language
        translated = GoogleTranslator(source='en', target=target_lang).translate(response_text)
        
        # If input was in Latin script, transliterate back
        if input_in_latin and target_lang in ['hi', 'mr']:
            return transliterate_to_latin(translated, target_lang)
        
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
        return response.text

    except Exception as e:
        print(f"[ERROR] Gemini call failed: {e}")
        return "I'm having trouble accessing company information right now. Please visit indeedinspiring.com for details."
    
def get_indeed_response(user_input):
    # Step 1: Detect input language
    input_lang = detect_language(user_input)
    print(f"[DEBUG] Input language detected: {input_lang}")
    
    # Step 2: Translate input to English for processing
    translated_input = translate_to_english(user_input, input_lang)
    if input_lang != "en":
        print(f"[DEBUG] Translated input to English: {translated_input}")

    # Step 3: Process the query (all internal processing remains in English)
    response = None

    # Handle name query
    name_queries = ["what is your name", "your name", "tumhara naam", "tuzhe nav", "नाव काय"]
    if any(query in translated_input.lower() for query in name_queries):
        print("[INFO] Response from: Name handler")
        base_response = f"My name is {CHATBOT_NAME}. How can I assist you with Indeed Inspiring Infotech?"
        if input_lang != "en":
            response = translate_response(base_response, input_lang, user_input)
        else:
            response = base_response

    # Handle knowledge base queries
    if not response:
        knowledge_response = search_knowledge(translated_input, indeed_kb)
        if knowledge_response:
            print("[INFO] Response from: Knowledge Base")
            if input_lang != "en":
                response = translate_response(knowledge_response, input_lang, user_input)
            else:
                response = knowledge_response

    # Handle greetings
    if not response:
        greeting_response = handle_time_based_greeting(translated_input)
        if greeting_response:
            print("[INFO] Response from: Time-Based Greeting")
            if input_lang != "en":
                response = translate_response(greeting_response, input_lang, user_input)
            else:
                response = greeting_response

    # Handle date queries
    if not response:
        date_response = handle_date_related_queries(translated_input)
        if date_response:
            print("[INFO] Response from: Date Handler")
            if input_lang != "en":
                response = translate_response(date_response, input_lang, user_input)
            else:
                response = date_response

    # Handle NLP generated responses
    if not response:
        nlp_response = generate_nlp_response(translated_input)
        if nlp_response:
            print("[INFO] Response from: NLP Generator")
            if input_lang != "en":
                response = translate_response(nlp_response, input_lang, user_input)
            else:
                response = nlp_response

    # Fallback to Gemini API
    if not response:
        print("[INFO] Response from: Gemini API")
        gemini_response = get_gemini_indeed_response(translated_input)
        if input_lang != "en":
            response = translate_response(gemini_response, input_lang, user_input)
        else:
            response = gemini_response

    print(f"[DEBUG] Final response: {response}")
    return response