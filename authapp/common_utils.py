import os
import json
import re
import random
import string
import logging
from datetime import datetime, timedelta
from fuzzywuzzy import fuzz
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import spacy
import nltk
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urldefrag
from .website_guide import get_website_guide_response
import time
from .hinglish_words import hinglish_words
from .minglish_words import minglish_words

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

# Initialize NLP and sentiment analysis
nlp = spacy.load("en_core_web_sm")
# nltk.download('wordnet')
sentiment_analyzer = SentimentIntensityAnalyzer()

# Language configuration
LANGUAGE_MAPPING = {
    'mr': 'marathi',
    'hi': 'hindi',
    'en': 'english'
}

SUPPORTED_LANGUAGES = ['en', 'hi', 'mr']  # Only these three base languages

# -------------------- JSON Loader --------------------
def load_json_data(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading {file_path}: {e}")
        return {}

def load_session_history(file_path):
    if os.path.exists(file_path):
        try:
            return load_json_data(file_path) or []
        except Exception:
            return []
    return []

def save_session_history(file_path, data):
    import os
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# -------------------- Conversational Enhancements --------------------
CONVERSATIONAL_FILLERS = {
    'thinking': ["Hmm...", "Let me think...", "That's interesting...", "Good question..."],
    'acknowledgement': ["I see.", "Right.", "Got it.", "Yeah.", "Understood."],
    'transition': ["Anyway,", "So,", "Well,", "Coming back to your question,"]
}

def add_conversational_pauses(response):
    """More controlled conversational fillers"""
    if random.random() < 0.25:  # Reduced chance
        filler = random.choice([
            "Hmm...", "Let me see...", 
            "That's a good question...",
            ""
        ])
        response = f"{filler} {response}".strip()
    
    return response

def add_occasional_typos(text):
    """More conservative typo simulation"""
    if random.random() < 0.03:  # Reduced from 5% to 3%
        words = text.split()
        if len(words) > 4:
            typo_index = random.randint(0, len(words)-1)
            if len(words[typo_index]) > 3:  # Only modify longer words
                words[typo_index] = words[typo_index][:-1]
                return ' '.join(words)
    return text

def should_add_follow_up(history):
    """Smarter follow-up decision making"""
    if len(history) < 2:
        return False
    last_query = history[-1]["user"].lower()
    return not any(kw in last_query for kw in ["bye", "exit", "stop"])

def vary_response_length(response):
    """Sometimes make responses longer or shorter"""
    if random.random() < 0.2:  # 20% chance
        if len(response.split()) > 10 and random.random() < 0.5:
            # Make a long response shorter
            return ' '.join(response.split()[:8]) + "..."
        else:
            # Make a short response longer
            additions = [
                " Let me know if you need more details.",
                " I can provide more information if you'd like.",
                " What else would you like to know?"
            ]
            return response + random.choice(additions)
    return response

def generate_response_variations(response, history):
    """Generate alternative versions of similar responses"""
    if not any(turn['bot'] == response for turn in history[-3:]):
        return response
    
    variations = [
        f"To reiterate, {response.lower()}",
        f"As mentioned, {response.lower()}",
        f"To expand on that, {response}",
        f"{response} Let me share some additional details...",
        f"Building on that, {response.lower()}"
    ]
    return random.choice(variations)

def get_proactive_question(history):
    """Generate a follow-up question to drive conversation"""
    if len(history) < 2:
        return None
    
    prompt = f"""
Based on this conversation history, suggest a natural follow-up question:
Conversation History:
{"\n".join([f"User: {turn['user']}\nBot: {turn['bot']}" for turn in history[-2:]])}

Suggested follow-up question (keep it very brief and natural):
"""
    try:
        # Placeholder: Replace with actual model call or API integration
        def call_mistral_model(prompt, max_tokens=20):
            # This is a stub. Replace with actual implementation.
            return "What else would you like to ask?"
        return call_mistral_model(prompt, max_tokens=20)
    except:
        return None
import traceback    
# -------------------- Knowledge Base Loader --------------------
def load_knowledge_base(file_path):
    print("load_knowledge_base() called from:")
    traceback.print_stack(limit=2)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # print(data)       
            
            # Get the list of intents
            intents = data.get('faqs', {}).get('intents', []) 
            knowledge_base = []
            for item in intents:
                entry = {
                    'tag': item.get('tag'),
                    'patterns': [k.lower() for k in item.get('patterns', [])],
                    'response': item.get('response', []),
                    'follow_up': item.get('follow_up', ''),
                    'next_suggestions': item.get('next_suggestions', [])
                }
                knowledge_base.append(entry)
            # print(type(knowledge_base))
            # print(knowledge_base) 
            return knowledge_base
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print("helo")
        logging.error(f"Error loading {file_path}: {e}")
        return []

# -------------------- Response Handlers --------------------
def handle_greetings(user_input, greetings_kb):
    normalized_input = user_input.lower()
    for greet in greetings_kb.get('inputs', []):
        if greet in normalized_input:
            return random.choice(greetings_kb.get('responses', []))
    return None


def handle_farewells(user_input, farewells_kb):
    normalized_input = user_input.lower()
    for farewell in farewells_kb.get('inputs', []):
        if farewell in normalized_input:
            return random.choice(farewells_kb.get('responses', []))
    return None

def handle_general(user_input, general_kb):
    normalized_input = user_input.lower()
    for phrase in general_kb.get('inputs', []):
        if phrase in normalized_input:
            return random.choice(general_kb.get('responses', []))
    return None


# -------------------- Knowledge Base Search --------------------
def search_knowledge_block(user_query, knowledge_base):
    user_query = user_query.lower()
    
    # 1. Exact match
    for entry in knowledge_base:
        for pattern in entry.get("patterns", []):
            if user_query == pattern.lower():
                print(f"[DEBUG] Response from EXACT MATCH: '{pattern}'")
                print(f"[AK] Matched entry: {entry}")
                return entry

    # 2. Substring or regex match
    for entry in knowledge_base:
        for pattern in entry.get("patterns", []):
            if re.search(re.escape(pattern.lower()), user_query):
                print(f"[DEBUG] Response from SUBSTRING/REGEX MATCH: '{pattern}'")
                print(f"[AK] Matched entry: {entry}")
                return entry

    # 3. Fuzzy match
    best_match = None
    best_score = 0
    for entry in knowledge_base:
        for pattern in entry.get("patterns", []):
            score = fuzz.ratio(user_query, pattern.lower())
            if score > best_score and score > 80:
                best_score = score
                best_match = entry
    
    if best_match:
        print(f"[DEBUG] Response from FUZZY MATCH (score: {best_score})")
    print(f"[AK] Matched entry: {best_match}")
    return best_match

# -------------------- Time & Date Utilities --------------------
from datetime import datetime

def handle_time_based_greeting(msg):
    greetings = ["good morning", "good afternoon", "good evening", "good night"]
    msg_lower = msg.lower()
    current_hour = datetime.now().hour

    for greeting in greetings:
        if greeting in msg_lower:
            if greeting == "good morning":
                return "Good morning! How can I assist you today?" if current_hour < 12 else "It's already past morning, but good day to you!"
            elif greeting == "good afternoon":
                return "Good afternoon! How can I assist you today?" if 12 <= current_hour < 18 else "It's not quite afternoon, but good day to you!"
            elif greeting == "good evening":
                if current_hour >= 22:
                    return "It's actually late night now! Good night and sleep well!"
                elif current_hour >= 18:
                    return "Good evening! How can I assist you today?"
                else:
                    return "It's not evening yet, but good day to you!"
            elif greeting == "good night":
                return "Good night! Sleep well and take care!" if current_hour >= 18 else "It's not night time yet, but have a great day!"

    if "current time" in msg_lower:
        return f"The current time is {datetime.now().strftime('%H:%M:%S')}."
    return None


def handle_date_related_queries(msg):
    msg_lower = msg.lower()
    today = datetime.now()

    date_mapping = {
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "day after tomorrow": today + timedelta(days=2),
        "yesterday": today - timedelta(days=1),
        "day before yesterday": today - timedelta(days=2),
        "next week": today + timedelta(weeks=1),
        "last week": today - timedelta(weeks=1),
        "next month": (today.replace(day=28) + timedelta(days=4)).replace(day=1),
        "last month": (today.replace(day=1) - timedelta(days=1)).replace(day=1),
        "next year": today.replace(year=today.year + 1),
        "last year": today.replace(year=today.year - 1)
    }

    for key, date in date_mapping.items():
        if key in msg_lower:
            if "date" in msg_lower:
                return f"The {key}'s date is {date.strftime('%B %d, %Y')}."
            elif "day" in msg_lower:
                return f"The {key} is {date.strftime('%A')}."

    return None

# -------------------- Website Crawler --------------------


def is_valid_page(url):
    allowed_extensions = ('.php', '.html', '.htm', '')  # Allow these
    disallowed_extensions = (
        '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico',
        '.pdf', '.zip', '.rar', '.mp4', '.mp3', '.wav',
        '.css', '.js', '.json', '.xml'
    )

    lower_url = url.lower()
    if any(lower_url.endswith(ext) for ext in disallowed_extensions):
        return False
    if '.' in lower_url:
        return any(lower_url.endswith(ext) for ext in allowed_extensions)
    return True

def crawl_website(base_url, max_pages=30):
    priority_keywords = [
        'about', 'who-we-are', 'vision-mission', 'the-founder', 'nature-education',
        'history', 'our-story', 'objectives', 'values', 'our-projects',
        'volunteer', 'impact', 'our-work', 'what-we-do', 'why-gmt'
    ]

    visited = set()
    to_visit = []
    priority_links = []
    normal_links = []
    result = []

    def normalize_url(url):
        return urldefrag(urljoin(base_url, url)).url.rstrip('/')

    def scrape_and_store(url):
        try:
            response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if 'text/html' not in response.headers.get('Content-Type', ''):
                print(f"[SKIPPED - Non-HTML] {url}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string.strip() if soup.title else "No Title"
            text = ' '.join(soup.stripped_strings)

            result.append({
                "url": url,
                "title": title,
                "Scraped text": text
            })

            links = []
            for tag in soup.find_all('a', href=True):
                link = normalize_url(tag['href'])
                if link.startswith(base_url) and is_valid_page(link) and link not in visited:
                    links.append(link)
            return links

        except Exception as e:
            logging.error(f"Error scraping {url}: {str(e)}")
            return []

    print(f"[CRAWL] Visiting: {base_url}")
    visited.add(base_url)
    links = scrape_and_store(base_url)

    for link in links:
        if any(keyword in link.lower() for keyword in priority_keywords):
            priority_links.append(link)
        else:
            normal_links.append(link)

    to_visit = priority_links + normal_links

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue
        print(f"[CRAWL] Visiting: {url}")
        visited.add(url)
        new_links = scrape_and_store(url)
        for link in new_links:
            if link not in visited and link not in to_visit:
                to_visit.append(link)

    print(f"[DONE] Total pages scraped: {len(result)}")
    return result

# -------------------- Website Content Matcher --------------------

from textblob import TextBlob

from rank_bm25 import BM25Okapi

def find_matching_content(user_input, indexed_content, threshold=0.6):
    """
    Uses BM25 ranking to find the most relevant page in the crawled content.
    Returns best match dict with url, title, and text snippet if score >= threshold.
    """
    # Step 1: Build corpus from crawled content
    corpus = []
    valid_pages = []
    
    for page in indexed_content:
        page_text = page.get("Scraped text", "")
        if page_text:
            tokens = page_text.lower().split()
            corpus.append(tokens)
            valid_pages.append(page)  # Keep aligned list for indexing
    
    if not corpus:
        return None  # No valid content to search

    # Step 2: Build BM25 index
    bm25 = BM25Okapi(corpus)

    # Step 3: Tokenize user query
    query_tokens = user_input.lower().split()

    # Step 4: Score all documents
    scores = bm25.get_scores(query_tokens)

    # Step 5: Find the best match
    best_index = scores.argmax()
    best_score = scores[best_index]

    if best_score >= threshold:
        best_page = valid_pages[best_index]
        print("best match type",type(best_page.get('Scraped text', '')[:1000]))
        return {
    'url': best_page.get('url', ''),
    'title': best_page.get('title', ''),
    'text': best_page.get('Scraped text', '')[:1000]
}

        
    
    return None



def get_contextual_response_from_website(user_input, indexed_content, threshold=0.6):
    """
    Returns matched page content (if any) from crawled data that can be passed to Gemini.
    """
    match = find_matching_content(user_input, indexed_content, threshold=threshold)
    if match:
        context_text = (
            f"Relevant information from website:\n"
            f"Title: {match['title']}\n"
            f"URL: {match['url']}\n"
            f"Content Snippet:\n{match['text']}\n"
        )
        print(context_text)
        return context_text
    print("[DEBUG] No matching content found for user input.\n")
    return None

# -------------------- Basic NLP Smalltalk --------------------
def generate_nlp_response(msg, bot_name="infi"):
    doc = nlp(msg)
    greetings = ["hi", "hello", "hey", "hii"]

    if any(token.lower_ in greetings for token in doc):
        return random.choice([f"Hello! I'm {bot_name}. How can I help you today?"])
    elif "how are you" in msg.lower():
        return random.choice(["I'm doing great, thanks for asking!", "I'm good! How about you?"])
    elif msg.lower() in ["great", "good", "awesome"]:
        return random.choice(["Glad to hear that!", "That's wonderful!"])
    elif "thank you" in msg.lower() or "thanks" in msg.lower():
        return random.choice(["You're welcome!", "Happy to help!"])
    elif "bye" in msg.lower() or "exit" in msg.lower():
        return "Goodbye! Have a great day!"

    return None


from deep_translator import GoogleTranslator
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

DEFAULT_LANG = "en"
SUPPORTED_LANGUAGES = ['en', 'hi', 'mr', 'ta', 'te', 'kn', 'gu', 'bn', 'pa', 'fr', 'de', 'es', 'ja', 'ko', 'zh']

LANGUAGE_MAPPING = {
    'mr': 'marathi',
    'hi': 'hindi',
    'en': 'english'
}
def detect_language(text):
    """Detect the base language of the input text (en, hi, or mr)"""
    try:
        lang = detect(text)
        return lang if lang in LANGUAGE_MAPPING else 'en'
    except LangDetectException as e:
        print(f"[LANG ERROR] Detection failed: {e}")
        return 'en'

def detect_input_script(text):
    """Detect if text is in English script or native script"""
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return 'english_script' if (ascii_chars / len(text)) > 0.7 else 'native_script'


def detect_input_language_type(text):
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return 'english_script' if (ascii_chars / len(text)) > 0.7 else 'native_script'

def contains_hinglish_keywords(text, hinglish_words):
    """Check if text contains Hinglish keywords"""
    words = re.findall(r'\b\w+\b', text.lower())
    return any(word in hinglish_words for word in words)

def detect_language_variant(text, hinglish_words, minglish_words):
    """
    Detect language variant considering:
    - English (en)
    - Hindi (hi)
    - Marathi (mr)
    - Hinglish (hi in English script with Hinglish words)
    - Minglish (mr in English script with Minglish words)
    """
    try:
        lang_code = detect(text)
        script_type = detect_input_script(text)

        # Hinglish detection
        if script_type == 'english_script' and contains_hinglish_keywords(text, hinglish_words):
            return 'hinglish'
        # Minglish detection
        elif script_type == 'english_script' and contains_minglish_keywords(text, minglish_words):
            return 'minglish'
        # Base languages
        elif lang_code in ['hi', 'mr', 'en']:
            return lang_code
        else:
            return 'en'
    except LangDetectException:
        return 'en'

def contains_minglish_keywords(text, minglish_words):
    """Check if text contains Minglish keywords"""
    words = re.findall(r'\b\w+\b', text.lower())
    return any(word in minglish_words for word in words)


def translate_response(response_text, target_lang, input_script_type):
    try:
        if target_lang == 'en':
            return response_text

        translated = GoogleTranslator(source='en', target=target_lang).translate(response_text)
        
        if input_script_type == 'english_script':
            try:
                return transliterate(translated, sanscript.DEVANAGARI, sanscript.ITRANS)
            except Exception as e:
                print(f"[ERROR] Transliteration failed: {e}")
                return translated
        else:
            return translated
    except Exception as e:
        print(f"[ERROR] Response translation failed: {e}")
        return response_text

    
def translate_to_english(text):
    """Translate text to English if it's not already English"""
    if not text or len(text.strip()) < 2:
        return text
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except Exception as e:
        print(f"[TRANS ERROR] To English failed: {e}")
        return text

def is_farewell(user_input):
    farewells = ["bye", "goodbye", "see you", "talk to you later", "farewell", "take care"]
    return any(phrase in user_input.lower() for phrase in farewells)


def translate_from_english(text, target_lang):
    if not text or len(text.strip()) < 2:
        return text
    try:
        return GoogleTranslator(source='en', target=target_lang).translate(text)
    except Exception as e:
        print(f"[ERROR] Translation from English failed: {e}")
        return text


# Conversation driving prompts
CONVERSATION_PROMPTS = {
    'intro': [
    "Would you like to know about our current plantation projects?",
    "I can tell you about our volunteer opportunities if you're interested?",
    "Would you like to hear about our upcoming events or how you can take part?"
],
'mid': [
    "Shall I share some success stories from our recent initiatives?",
    "Do you want to learn how we plant trees step by step?",
    "I could also share some interesting facts about Peepal trees if you'd like?"
],
'closing': [
    "Would you like to know about the services we offer to measure the impact of trees?",
    "Are you interested in trainings on how to calculate the benefits of trees using i-Tree software?",
    "Would you like me to send you more information via email?"
]
}

def get_conversation_driver(history, stage):
    """Generate context-aware conversation drivers"""

    if len(history) < 2:
        return random.choice(CONVERSATION_PROMPTS['intro'])

    
    last_question = history[-1]["user"]
    last_question=last_question.lower()
    
    if any(kw in last_question for kw in ["thank", "bye", "enough"]):
        return random.choice(CONVERSATION_PROMPTS['closing'])
    
    if len(history) > 4:
        return random.choice(CONVERSATION_PROMPTS['mid'])
    
    # Default follow-up based on context
    context_keywords = ["plant", "tree", "volunteer", "donat", "project"]
    for kw in context_keywords:
        if kw in last_question:
            return f"Would you like more details about our {kw} programs?"
    
    return random.choice(CONVERSATION_PROMPTS['mid'])

INDEED_CONVERSATION_PROMPTS = {
    'intro': [
        "Would you like to know about our IT services and solutions?",
        "I can tell you about our technology expertise if you're interested?",
        "Shall I share some of our recent client success stories?"
    ],
    'mid': [
        "What interests you most - our AI solutions, web development, or digital transformation services?",
        "Would you like details about any specific technology we specialize in?",
        "I could also share information about our team's expertise if you'd like?"
    ],
    'closing': [
        "Before we finish, is there anything else about Indeed Inspiring Infotech you'd like to know?",
        "Would you like to know more about the kinds of student and faculty engagement activities we organize?",
        "Should I email you more information about our services?"
    ]
}

def get_indeed_conversation_driver(history, stage):
    """Generate context-aware conversation drivers for Indeed Inspiring Infotech"""
    if len(history) < 2:
        return random.choice(INDEED_CONVERSATION_PROMPTS['intro'])
    
    last_question = history[-1]["user"].lower()
    
    if any(kw in last_question for kw in ["thank", "bye", "enough"]):
        return random.choice(INDEED_CONVERSATION_PROMPTS['closing'])
    
    if len(history) > 4:
        return random.choice(INDEED_CONVERSATION_PROMPTS['mid'])
    
    # Tech-focused follow-ups
    tech_keywords = {
        'ai': ['ai', 'artificial intelligence', 'machine learning', 'ml'],
        'web': ['web', 'website', 'frontend', 'backend'],
        'digital': ['digital', 'transformation', 'dx'],
        'cloud': ['cloud', 'aws', 'azure', 'gcp']
    }
    
    for tech, keywords in tech_keywords.items():
        if any(kw in last_question for kw in keywords):
            return random.choice(INDEED_CONVERSATION_PROMPTS['tech_focus']).format(tech)
    
    # Business-focused follow-ups
    business_keywords = ['service', 'solution', 'product', 'offer']
    if any(kw in last_question for kw in business_keywords):
        return "Would you like to know more about how we tailor solutions for specific industries?"
    
    return random.choice(INDEED_CONVERSATION_PROMPTS['mid'])

# -------------------- Miscellaneous Utilities --------------------
# Add to common_utils.py
CONTACT_EMAIL = "iipt.aiml@gmail.com"

def is_contact_request(text):
    """Check if user wants to connect/contact"""
    contact_keywords = [
        'contact', 'connect', 'reach out', 'talk to someone',
        'email', 'phone', 'number', 'speak with'
    ]
    return any(keyword in text.lower() for keyword in contact_keywords)

def is_info_request(text):
    """Check if user is providing information"""
    info_keywords = [
        'my name is', 'i am', 'email is', 'contact is',
        'you can reach me at', 'my number is'
    ]
    return any(keyword in text.lower() for keyword in info_keywords)


MISTRAL_API_KEYS = [
    "3OyOnjAypy79EewldzfcBczW01mET0fM",
    "tZKRscT6hDUurE5B7ex5j657ZZQDQw3P",
    "dvXrS6kbeYxqBGXR35WzM0zMs4Nrbco2",
    "5jMPffjLAwLyyuj6ZwFHhbLZxb2TyfUR"
]

def call_mistral_model(prompt, max_tokens=100):
    url = "https://api.mistral.ai/v1/chat/completions"
    payload = {
        "model": "mistral-small",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": max_tokens
    }

    # Rotate through keys until one succeeds
    for api_key in MISTRAL_API_KEYS:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        # print(f"[DEBUG] Using API Key: {api_key}")

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content'].strip()
            else:
                print(f"[ERROR] Failed with key {api_key}: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"[EXCEPTION] Error using key {api_key}: {e}")

    return "I'm having trouble accessing information right now. Please try again later."


