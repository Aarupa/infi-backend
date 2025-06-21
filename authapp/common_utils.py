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

# Initialize NLP and sentiment analysis
nlp = spacy.load("en_core_web_sm")
# nltk.download('wordnet')
sentiment_analyzer = SentimentIntensityAnalyzer()

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

def save_session_history(file_path, history):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(history[-5:], f, indent=2)
        
# -------------------- Knowledge Base Loader --------------------
def load_knowledge_base(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            knowledge_base = []
            for item in data.get('faqs', []):
                entry = {
                    'question': item['question'],
                    'keywords': [k.lower() for k in item.get('keywords', [])],
                    'responses': item['responses'],
                    'patterns': [re.compile(r'\b' + re.escape(k) + r'\b', re.IGNORECASE)
                                 for k in item.get('keywords', [])]
                }
                knowledge_base.append(entry)
            return knowledge_base
    except (FileNotFoundError, json.JSONDecodeError) as e:
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
def search_knowledge(query, knowledge_base):
    query = query.lower()

    for entry in knowledge_base:
        if entry['question'].lower() == query:
            return random.choice(entry['responses'])

    for entry in knowledge_base:
        for pattern in entry['patterns']:
            if pattern.search(query):
                return random.choice(entry['responses'])

    best_match = None
    best_score = 0
    for entry in knowledge_base:
        for keyword in entry['keywords']:
            score = fuzz.ratio(query, keyword)
            if score > best_score and score > 70:
                best_score = score
                best_match = entry

    return random.choice(best_match['responses']) if best_match else None

# -------------------- Time & Date Utilities --------------------
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
                return "Good evening! How can I assist you today?" if current_hour >= 18 else "It's not evening yet, but good day to you!"
            elif greeting == "good night":
                return "Good night! Sleep well and take care!"

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

    indexed_content = {}
    visited = set()
    to_visit = []
    priority_links = []
    normal_links = []

    def normalize_url(url):
        return urldefrag(urljoin(base_url, url)).url.rstrip('/')

    print(f"[CRAWL] Visiting: {base_url}")
    try:
        response = requests.get(base_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if 'text/html' not in response.headers.get('Content-Type', ''):
            print(f"[SKIPPED - Non-HTML] {base_url}")
            return indexed_content

        soup = BeautifulSoup(response.text, 'html.parser')
        indexed_content[base_url] = {
            'title': soup.title.string if soup.title else 'No Title',
            'text': ' '.join(soup.stripped_strings),
            'links': []
        }
        visited.add(base_url)

        # Categorize links by priority
        for tag in soup.find_all('a', href=True):
            link = normalize_url(tag['href'])
            if link.startswith(base_url) and is_valid_page(link):
                indexed_content[base_url]['links'].append(link)
                if link in visited:
                    continue
                if any(keyword in link.lower() for keyword in priority_keywords):
                    priority_links.append(link)
                else:
                    normal_links.append(link)
    except Exception as e:
        logging.error(f"Error crawling {base_url}: {str(e)}")
        return indexed_content

    to_visit = priority_links + normal_links

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue

        print(f"[CRAWL] Visiting: {url}")
        try:
            response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if 'text/html' not in response.headers.get('Content-Type', ''):
                print(f"[SKIPPED - Non-HTML] {url}")
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            indexed_content[url] = {
                'title': soup.title.string if soup.title else 'No Title',
                'text': ' '.join(soup.stripped_strings),
                'links': []
            }

            for tag in soup.find_all('a', href=True):
                link = normalize_url(tag['href'])
                if link.startswith(base_url) and is_valid_page(link) and link not in visited:
                    indexed_content[url]['links'].append(link)
                    if link not in to_visit:
                        to_visit.append(link)

            visited.add(url)
        except Exception as e:
            logging.error(f"Error crawling {url}: {str(e)}")

    print(f"[DONE] Total pages crawled: {len(indexed_content)}")
    return indexed_content


# -------------------- Website Content Matcher --------------------

def find_matching_content(user_input, indexed_content, threshold=0.6):
    """
    Search crawled content for a match to the user input.
    Returns the best matching content (title + paragraph) if found.
    """
    best_match = None
    best_score = 0

    user_input_blob = TextBlob(user_input)
    input_keywords = set(word.lower() for word in user_input_blob.words if len(word) > 3)

    for url, page in indexed_content.items():
        page_text = page.get("text", "")
        if not page_text:
            continue

        # Basic scoring by keyword overlap
        page_words = set(page_text.lower().split())
        common_keywords = input_keywords & page_words
        score = len(common_keywords) / (len(input_keywords) or 1)

        if score > best_score:
            best_score = score
            best_match = {
                'url': url,
                'title': page.get('title', ''),
                'text': page_text[:1000]  # Limit to avoid overloading Gemini
            }

    return best_match if best_score >= threshold else None



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
        return context_text
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

def detect_language(text):
    try:
        lang = detect(text)
        return lang if lang in LANGUAGE_MAPPING else 'en'
    except LangDetectException as e:
        print(f"[ERROR] Language detection failed: {e}")
        return 'en'


def translate_to_english(text):
    if not text or len(text.strip()) < 2:
        return text
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except Exception as e:
        print(f"[ERROR] Translation to English failed: {e}")
        return text

def translate_from_english(text, target_lang):
    if not text or len(text.strip()) < 2:
        return text
    try:
        return GoogleTranslator(source='en', target=target_lang).translate(text)
    except Exception as e:
        print(f"[ERROR] Translation from English failed: {e}")
        return text
