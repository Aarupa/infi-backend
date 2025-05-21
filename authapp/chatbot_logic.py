import os
import json
import random
import re
import tempfile
import logging
from datetime import datetime, timedelta
import string
import threading
import time
from fuzzywuzzy import fuzz, process
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer # type: ignore
from fuzzywuzzy import fuzz, process
from pydub import AudioSegment
from pydub.playback import play
from gtts import gTTS
import whisper
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import spacy
import nltk
import google.generativeai as genai

# Django imports
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

# -------------------- Constants --------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
json_dir = os.path.join(script_dir, 'json_files')
os.makedirs(json_dir, exist_ok=True)

# Ensure required JSON files exist with default content
default_files = {
    'indeed_knowledge.json': {"faqs": []},
    'gmtt_knowledge.json': {"faqs": []}
}
for filename, default_content in default_files.items():
    file_path = os.path.join(json_dir, filename)
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(default_content, f, indent=4, ensure_ascii=False)
json_path = os.path.join(json_dir, 'content.json')
dialogue_history_path = os.path.join(json_dir, 'history.json')
greetings_path = os.path.join(json_dir, 'greetings.json')
farewells_path = os.path.join(json_dir, 'farewells.json')
general_path = os.path.join(json_dir, 'general.json')
trees_path = os.path.join(json_dir, 'trees.json')

# Initialize NLP and sentiment analysis tools
nlp = spacy.load("en_core_web_sm")
nltk.download('wordnet')
sentiment_analyzer = SentimentIntensityAnalyzer()

# Load data files
def load_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

faq_data = load_json_file(json_path)
greetings_data = load_json_file(greetings_path)
farewells_data = load_json_file(farewells_path)
general_data = load_json_file(general_path)
trees_data = load_json_file(trees_path)

# Conversation history
conversation_history = []
history = load_json_file(dialogue_history_path)

# Clear history.json for one-time use
with open(dialogue_history_path, 'w', encoding='utf-8') as f:
    json.dump({}, f, indent=4, ensure_ascii=False)

# Load Whisper model
whisper_model = whisper.load_model("tiny")

# Chatbot names
CHATBOT_NAME = "Infi"
GMTT_NAME = "Infi"

# Gemini API configuration
API_KEY = "AIzaSyA4bFTPKOQ3O4iKLmvQgys_ZjH_J1MnTUs"

# -------------------- File Paths --------------------
paths = {
    'indeed_kb': os.path.join(script_dir, 'json_files', 'indeed_knowledge.json'),
    'gmtt_kb': os.path.join(script_dir, 'json_files', 'gmtt_knowledge.json'),
    'history': os.path.join(script_dir, 'json_files', 'history.json'),
    'greetings': os.path.join(script_dir, 'json_files', 'greetings.json'),
    'farewells': os.path.join(script_dir, 'json_files', 'farewells.json'),
    'general': os.path.join(script_dir, 'json_files', 'general.json')
}

# -------------------- Initialize Services --------------------
genai.configure(api_key=API_KEY)
conversation_history = []



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

# Load knowledge bases
indeed_kb = load_knowledge_base(paths['indeed_kb'])
gmtt_kb = load_knowledge_base(paths['gmtt_kb'])



def load_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# -------------------- Website Crawler --------------------
def crawl_website(base_url, max_pages=10):
    """Crawl the website and index all page content"""
    indexed_content = {}
    visited = set()
    to_visit = [base_url]
    
    while to_visit and len(visited) < max_pages:
        url = to_visit.pop()
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            indexed_content[url] = {
                'title': soup.title.string if soup.title else 'No Title',
                'text': ' '.join(soup.stripped_strings),
                'links': []
            }
            
            for link in soup.find_all('a', href=True):
                absolute_url = urljoin(base_url, link['href'])
                if absolute_url.startswith(base_url) and absolute_url not in visited:
                    indexed_content[url]['links'].append(absolute_url)
                    if absolute_url not in to_visit:
                        to_visit.append(absolute_url)
            
            visited.add(url)
        except Exception as e:
            logging.error(f"Error crawling {url}: {str(e)}")
    
    return indexed_content

# Initialize website indexes
INDEED_INDEX = crawl_website("https://indeedinspiring.com")
GMTT_INDEX = crawl_website("https://www.givemetrees.org")

# -------------------- Utility Functions --------------------
def save_conversation(user_message, response):
    history = load_json_file(paths['history'])
    history[user_message] = response
    with open(paths['history'], 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=4, ensure_ascii=False)

def correct_spelling(query):
    """Correct spelling mistakes in the user query using TextBlob."""
    blob = TextBlob(query)
    return str(blob.correct())

def get_best_match(query, choices, threshold=80, min_length=2):
    """Find the best matching keyword using fuzzy string matching."""
    if len(query) < min_length:
        return None
    best_match, score = process.extractOne(query, choices)
    return best_match if score >= threshold else None

def analyze_sentiment(msg):
    """Analyze the sentiment of a user message using VaderSentiment."""
    score = sentiment_analyzer.polarity_scores(msg)['compound']
    if score >= 0.5:
        return "positive"
    elif score <= -0.5:
        return "negative"
    return "neutral"

def enhance_speech_recognition(text):
    """Advanced correction for speech recognition variations"""
    corrections = [
        (r"\b(indian|india|indeedin|indie)\s*(inspiring|spring)\s*(infotech|info tech)?\b", 
         "Indeed Inspiring Infotech"),
        (r"\b(indeed|indian)\s*(infotech|info tech)\b", 
         "Indeed Infotech"),
        (r"\b(give me|get me|i need)\s*(trees|tree|plants)\b",
         "Give Me Trees"),
        (r"\b(environment|eco|green)\s*(foundation|org|charity)\b",
         "Give Me Trees Foundation")
    ]
    
    for pattern, replacement in corrections:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text.strip()

# -------------------- Shared Conversation Handlers --------------------
def handle_time_based_greeting(msg):
    """Handle time-based greetings and provide an appropriate response."""
    greetings = ["good morning", "good afternoon", "good evening", "good night"]
    msg_lower = msg.lower()

    for greeting in greetings:
        if greeting in msg_lower:
            current_hour = datetime.now().hour
            if greeting == "good morning":
                if current_hour < 12:
                    return "Good morning! How can I assist you today?"
                elif current_hour < 18:
                    return "It's already afternoon, but good day to you!"
                else:
                    return "It's evening now, but good day to you!"
            elif greeting == "good afternoon":
                if current_hour < 12:
                    return "It's still morning, but good day to you!"
                elif current_hour < 18:
                    return "Good afternoon! How can I assist you today?"
                else:
                    return "It's evening now, but good day to you!"
            elif greeting == "good evening":
                if current_hour < 12:
                    return "It's still morning, but good day to you!"
                elif current_hour < 18:
                    return "It's still afternoon, but good day to you!"
                else:
                    return "Good evening! How can I assist you today?"
            elif greeting == "good night":
                return "Good night! Sleep well and take care!"

    if "current time" in msg_lower:
        return f"The current time is {datetime.now().strftime('%H:%M:%S')}."

    return None

def handle_date_related_queries(msg):
    """Handle date-related queries and provide an appropriate response."""
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

# -------------------- Knowledge Search --------------------
def search_knowledge(query, knowledge_base):
    query = query.lower()
    
    # Check exact matches first
    for entry in knowledge_base:
        if entry['question'].lower() == query:
            return random.choice(entry['responses'])
    
    # Check keyword patterns
    for entry in knowledge_base:
        for pattern in entry['patterns']:
            if pattern.search(query):
                return random.choice(entry['responses'])
    
    # Fuzzy match fallback
    best_match = None
    best_score = 0
    for entry in knowledge_base:
        for keyword in entry['keywords']:
            score = fuzz.ratio(query, keyword)
            if score > best_score and score > 70:
                best_score = score
                best_match = entry
    
    return random.choice(best_match['responses']) if best_match else None

# -------------------- Chatbot Handlers --------------------
def handle_general_conversation(message):
    message = message.lower()
    
    # Time-based
    current_hour = datetime.now().hour
    if "good morning" in message:
        return "Good morning!" if current_hour < 12 else "It's actually afternoon, but hello!"
    elif "good afternoon" in message:
        return "Good afternoon!" if 12 <= current_hour < 18 else "It's actually evening, but hello!"
    
    # Date-based
    today = datetime.now()
    if "today" in message:
        return f"Today is {today.strftime('%A, %B %d, %Y')}"
    
    # Greetings
    greetings = load_json_file(paths['greetings']).get('greetings', {})
    if message in greetings.get('inputs', []):
        return random.choice(greetings.get('responses', []))
    
    return None

def generate_nlp_response(msg):
    """Generate a basic NLP response for general conversation."""
    doc = nlp(msg)
    greetings = ["hi", "hello", "hey", "hii"]
    
    if any(token.lower_ in greetings for token in doc):
        return random.choice([f"Hello! I'm {CHATBOT_NAME}. How can I help you today?", 
                             f"Hi there! I'm {GMTT_NAME} here to help with tree conservation!"])
    
    # Rest of the function remains the same...
    elif "how are you" in msg.lower():
        return random.choice(["I'm doing great, thanks for asking!", "I'm good! How about you?"])
    elif msg.lower() in ["great", "good", "awesome"]:
        return random.choice(["Glad to hear that!", "That's wonderful!"])
    elif "thank you" in msg.lower() or "thanks" in msg.lower():
        return random.choice(["You're welcome!", "Happy to help!"])
    elif "bye" in msg.lower() or "exit" in msg.lower():
        conversation_history.clear()
        return "Goodbye! Have a great day!"
    
    return None

def get_priority_response(preprocessed_input):
    """Check if the input matches greetings, farewells, or general responses."""
    normalized_input = preprocessed_input.translate(str.maketrans('', '', string.punctuation)).lower()
    
    for category, data in [("greetings", greetings_data.get("greetings", {})),
                           ("farewells", farewells_data.get("farewells", {})),
                           ("general", general_data.get("general", {}))]:
        if normalized_input in map(str.lower, data.get("inputs", [])):
            return random.choice(data.get("responses", []))
    
    return None

def handle_general_conversation(user_message):
    """Handle general conversation that both chatbots should respond to"""
    handlers = [
        handle_time_based_greeting,
        handle_date_related_queries,
        generate_nlp_response,
        get_priority_response
    ]
    
    for handler in handlers:
        response = handler(user_message)
        if response:
            return response
    
    return None

# -------------------- Indeed Inspiring Chatbot --------------------
def get_company_response(query):
    """Handle company-specific questions"""
    query = enhance_speech_recognition(query.lower())
    
    faq_mapping = {
        r"(founder|who\s*started|ceo|owner)": 
            "Indeed Inspiring Infotech was founded by Mr. Kushal Sharma.",
        r"(contact|reach|phone|email|address)": 
            "You can contact us at:\nPhone: +1 (123) 456-7890\nEmail: info@indeedinspiring.com",
        r"(services|offerings|what\s*you\s*do)":
            "We specialize in AI solutions, web development, and digital transformation services.",
        r"(about|information|tell\s*me\s*about)":
            "Indeed Inspiring Infotech is a technology company focused on innovative IT solutions."
    }
    
    for pattern, response in faq_mapping.items():
        if re.search(pattern, query):
            return response
    
    return None

def get_gemini_indeed_response(user_query):
    """Get response using Gemini with Indeed website context"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Find most relevant page content from crawled website
        best_match = None
        best_score = 0
        query_keywords = set(user_query.lower().split())
        
        for url, data in INDEED_INDEX.items():
            page_keywords = set(data['text'].lower().split())
            match_score = len(query_keywords & page_keywords)
            if match_score > best_score:
                best_match = data
                best_score = match_score
        
        # Prepare context - start with basic company info
        context = """
        Indeed Inspiring Infotech is a technology company providing innovative IT solutions.
        Key Information:
        - Founded by Kushal Sharma
        - Specializes in AI, web development, and digital transformation
        - Website: https://indeedinspiring.com
        """
        
        # Add relevant page content if found
        if best_match and best_score > 2:  # Minimum keyword matches
            context += f"\n\nRelevant page content from {best_match['title']}:\n{best_match['text'][:2000]}..."
        
        prompt = f"""You are a specialist assistant for Indeed Inspiring Infotech.
        Strict Rules:
        1. Only provide information about Indeed Inspiring Infotech and its services
        2. For other topics, respond "I specialize in Indeed Inspiring Infotech related questions"
        3. Keep responses concise (1 sentences maximum)
        4. Always mention to visit indeedinspiring.com for more details
        5. If you don't know the answer, say "I'm still learning about this topic. Please check our website indeedinspiring.com"
        
        Context: {context}
        
        User Query: {user_query}
        
        Response:"""
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return "I'm having trouble accessing company information right now. Please visit indeedinspiring.com for details."

def get_indeed_response(user_input):
    """Complete Indeed chatbot response pipeline"""
    # Handle name question first
    if "what is your name" in user_input.lower() or "your name" in user_input.lower():
        return f"My name is {CHATBOT_NAME}. How can I assist you with Indeed Inspiring Infotech?"
    
    # 1. Handle general conversation
    # general_response = handle_general_conversation(user_input)
    # if general_response:
    #     return general_response
    
    # # 2. Check for company-specific responses
    # company_response = get_company_response(user_input)
    # if company_response:
    #     return company_response
    
    # # 3. Fallback to Gemini with Indeed context
    # return get_gemini_indeed_response(user_input)
    kb_response = search_knowledge(user_input, indeed_kb)
    if kb_response:
        return kb_response
    
    # Handle general conversation
    general_response = handle_general_conversation(user_input)
    if general_response:
        return general_response
    
    # Fallback to Gemini
    # return get_gemini_response(user_input, "Indeed Inspiring Infotech")
    return get_gemini_indeed_response(user_input)

# -------------------- Give Me Trees Chatbot --------------------
def get_trees_response(query):
    # """Get response from trees.json data"""
    # if not trees_data:
    #     return None
        
    # query = query.translate(str.maketrans('', '', string.punctuation)).lower()
    
    # # Check exact matches
    # for item in trees_data.get('faqs', []):
    #     if query == item['question'].lower():
    #         return random.choice(item['responses'])
    
    # # Check keywords
    # best_match = None
    # best_score = 0
    
    # for item in trees_data.get('faqs', []):
    #     for keyword in item.get('keywords', []):
    #         score = fuzz.ratio(query, keyword.lower())
    #         if score > best_score and score > 70:
    #             best_score = score
    #             best_match = item
    
    # if best_match:
    #     return random.choice(best_match['responses'])
    
    # return None

    query = query.translate(str.maketrans('', '', string.punctuation)).lower()
    
    # Handle identity questions
    identity_phrases = [
        "what is your name",
        "who are you",
        "your foundation",
        "your organization",
        "about you",
        "location of your",
        "address of your"
    ]
    
    if any(phrase in query for phrase in identity_phrases):
        kb_response = search_knowledge(query, gmtt_kb)
        if kb_response:
            return kb_response
        if "name" in query:
            return f"My name is {GMTT_NAME}."
        if "location" in query or "address" in query:
            return "We're headquartered in New Delhi, India."
        return "I represent Give Me Trees Foundation."
    
    # Check knowledge base
    kb_response = search_knowledge(query, gmtt_kb)
    if kb_response:
        return kb_response
    
    # General conversation
    general_response = handle_general_conversation(query)
    if general_response:
        return general_response
    
    # Fallback to Gemini
    return get_gemini_gmtt_response(query)


def save_conversation_to_file(user_message, response):
    """Save the conversation to a JSON file as key-value pairs."""
    history[user_message] = response
    with open(dialogue_history_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=4, ensure_ascii=False)

def get_gemini_gmtt_response(user_query):
    """Get trees-specific response from Gemini"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
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
        Give Me Trees Foundation is a non-profit organization dedicated to environmental conservation through tree planting.
        Key Information:
        - Founded in 1978 by Kuldeep Bharti
        - Headquarters in New Delhi, India
        - Planted over 20 million trees
        - Focus areas: Urban greening, rural afforestation, environmental education
        - Website: https://www.givemetrees.org
        """
        
        if best_match and best_score > 2:
            context += f"\n\nRelevant page content from {best_match['title']}:\n{best_match['text'][:2000]}..."
        
        # query =f" {user_query} give me trees"
        prompt = f"""You are a specialist assistant for Give Me Trees Foundation.
        Rules:
        1. Only provide information about tree planting and environmental conservation
        2. For other topics, respond "I specialize in tree-related questions"
        3. Keep responses under 3 sentences
        4. Always mention the website givemetrees.org
        
        Context: {context}

        Query: {user_query}

        Response:"""
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return "I'm having trouble accessing tree information right now. Please visit givemetrees.org for details."

def get_gmtt_response(user_input):
    """Complete GMTT chatbot response pipeline"""
    # Handle name question first
    if "what is your name" in user_input.lower() or "your name" in user_input.lower():
        return f"My name is {GMTT_NAME}. I'm here to help with Give Me Trees Foundation queries."
    
    # 1. Handle general conversation
    general_response = handle_general_conversation(user_input)
    if general_response:
        return general_response
    
    # 2. Check if this is a trees-related query
    tree_keywords = ["tree", "plant", "forest", "environment", "gmtt", "give me trees"]
    if not any(keyword in user_input.lower() for keyword in tree_keywords):
        return f"I'm {GMTT_NAME}, the Give Me Trees specialist. How can I help you with tree planting or environmental conservation today?"
    
    # 3. Check for trees-specific responses
    trees_response = get_trees_response(user_input)
    if trees_response:
        return trees_response
    
    # 4. Fallback to Gemini with trees context
    return get_gemini_gmtt_response(user_input)

# -------------------- HTTP Request Handlers --------------------
@csrf_exempt
def get_response(request):
    """Indeed chatbot endpoint"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('prompt', '')
            
            if user_message:
                bot_response = get_indeed_response(user_message)
                save_conversation_to_file(user_message, bot_response)
                return JsonResponse({'text': bot_response})
                
        except Exception as e:
            logging.error(f"Error in Indeed response: {e}")
            return JsonResponse({'text': 'Sorry, I encountered an error'}, status=500)
    
    return JsonResponse({'text': 'Invalid request'}, status=400)

@csrf_exempt
def gmtt_response(request):
    """Give Me Trees chatbot endpoint"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('prompt', '')
            
            if user_message:
                bot_response = get_gmtt_response(user_message)
                return JsonResponse({'text': bot_response})
                
        except Exception as e:
            logging.error(f"Error in GMTT response: {e}")
            return JsonResponse({
                'text': "Sorry, I encountered an error processing your trees-related request."
            }, status=500)
    
    return JsonResponse({'text': 'Invalid request method'}, status=400)

# def chat(request):
#     """Render Indeed chatbot interface"""
#     return render(request, 'chatbot.html')

# def gmtt(request):
#     """Render GMTT chatbot interface"""
#     return render(request, 'give_me_tree.html')

# -------------------- Background Services --------------------
def refresh_website_content():
    """Periodically update website content for both chatbots"""
    while True:
        global INDEED_INDEX, GMTT_INDEX
        INDEED_INDEX = crawl_website("https://indeedinspiring.com")
        GMTT_INDEX = crawl_website("https://www.givemetrees.org")
        time.sleep(86400)  # Refresh daily

# Start background thread
refresh_thread = threading.Thread(target=refresh_website_content, daemon=True)
refresh_thread.start()