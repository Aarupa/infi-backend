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
import time

# Initialize NLP and sentiment analysis
nlp = spacy.load("en_core_web_sm")
# nltk.download('wordnet')
sentiment_analyzer = SentimentIntensityAnalyzer()

# List of API keys to rotate through
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
        print(f"[DEBUG] Using API Key: {api_key}")

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content'].strip()
            else:
                print(f"[ERROR] Failed with key {api_key}: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"[EXCEPTION] Error using key {api_key}: {e}")

    return "I'm having trouble accessing information right now. Please try again later."

def is_mistral_follow_up(bot_message: str) -> bool:
   
    prompt = f"""
        You are an expert in analyzing chatbot conversations.

        Determine if the following chatbot message is a follow-up question.

        Definition:
        A follow-up question encourages the user to respond with interest, elaboration, or permission to continue.
        It may sound like: "Would you like to know more?", "Shall I explain further?", or "Do you want details?"

        Chatbot message:
        "{bot_message}"

        Answer only with "YES" or "NO".
        """

    try:
        response = call_mistral_model(prompt).strip().upper()
        match = re.search(r'\b(YES|NO)\b', response)
        return match.group(1) == "YES" if match else False

    except Exception as e:
        print(f"[ERROR] Failed to determine follow-up status: {e}")
        return False
    
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
                return entry

    # 2. Substring or regex match
    for entry in knowledge_base:
        for pattern in entry.get("patterns", []):
            if re.search(re.escape(pattern.lower()), user_query):
                print(f"[DEBUG] Response from SUBSTRING/REGEX MATCH: '{pattern}'")
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
    
    return best_match

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
        "Shall I share some success stories from our recent initiatives?"
    ],
    'mid': [
        "What aspect interests you most - our methodology, impact, or how to get involved?",
        "Would you like details about any specific region we work in?",
        "I could also share some interesting facts about Peepal trees if you'd like?"
    ],
    'closing': [
        "Before we wrap up, is there anything else you'd like to know?",
        "Would you like me to send you more information via email?",
        "Shall I connect you with our volunteer coordinator?"
    ]
}

def get_conversation_driver(history, stage):
    """Generate context-aware conversation drivers"""
    if len(history) < 2:
        return random.choice(CONVERSATION_PROMPTS['intro'])
    
    last_question = history[-1]["user"].lower()
    
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
        "Would you like me to connect you with our solutions team?",
        "Should I email you more information about our services?"
    ],
    'tech_focus': [
        "Would you like more details about our {0} implementations?",
        "I can share some case studies of our {0} projects if you're interested?",
        "Our {0} expertise is particularly strong - would you like to know more?"
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