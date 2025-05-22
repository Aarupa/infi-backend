import os
import json
import random
import re
import logging
from datetime import datetime, timedelta
import string
import threading
import time
from fuzzywuzzy import fuzz, process
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
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
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# -------------------- Initialization --------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
json_dir = os.path.join(script_dir, 'json_files')
os.makedirs(json_dir, exist_ok=True)

# Load NLP models
nlp = spacy.load("en_core_web_sm")
nltk.download('punkt')
sentiment_analyzer = SentimentIntensityAnalyzer()

# Chatbot identities
INDEED_CONFIG = {
    'name': "Infi",
    'org_name': "Indeed Inspiring Infotech",
    'org_type': "company",
    'kb_file': 'indeed_knowledge.json',
    'content_file': 'indeed_content.json',
    'website': "https://indeedinspiring.com",
    'founder': "Mr. Kushal Sharma",
    'services': ["AI solutions", "web development", "digital transformation"]
}

GMTT_CONFIG = {
    'name': "TreeBot",
    'org_name': "Give Me Trees Foundation",
    'org_type': "foundation",
    'kb_file': 'gmtt_knowledge.json',
    'content_file': 'gmtt_content.json',
    'website': "https://www.givemetrees.org",
    'founder': "Kuldeep Bharti",
    'services': ["tree planting", "environmental conservation", "urban greening"]
}

# Initialize Gemini
genai.configure(api_key="AIzaSyA4bFTPKOQ3O4iKLmvQgys_ZjH_J1MnTUs")

# -------------------- Utility Functions --------------------
def load_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json_file(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def correct_spelling(text):
    return str(TextBlob(text).correct())

def analyze_sentiment(text):
    score = sentiment_analyzer.polarity_scores(text)['compound']
    return "positive" if score >= 0.5 else "negative" if score <= -0.5 else "neutral"

# -------------------- Website Crawler --------------------
def crawl_and_save_website(base_url, config):
    """Crawl website and save content to JSON file"""
    indexed_content = {}
    visited = set()
    to_visit = [base_url]
    
    while to_visit and len(visited) < 10:
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
    
    # Save crawled content
    content_path = os.path.join(json_dir, config['content_file'])
    save_json_file(content_path, indexed_content)
    
    return indexed_content

# -------------------- Knowledge Management --------------------
def load_knowledge_base(config):
    """Load knowledge base with enhanced patterns"""
    kb_path = os.path.join(json_dir, config['kb_file'])
    kb_data = load_json_file(kb_path)
    
    knowledge_base = []
    for item in kb_data.get('faqs', []):
        entry = {
            'question': item['question'],
            'responses': item['responses'],
            'patterns': [re.compile(r'\b' + re.escape(k) + r'\b', re.IGNORECASE) 
                        for k in item.get('keywords', [])],
            'triggers': item.get('triggers', [])
        }
        knowledge_base.append(entry)
    
    # Add default organization questions
    org_questions = [
        {
            'question': f"What is {config['org_name']}?",
            'responses': [
                f"I'm part of {config['org_name']}, a {config['org_type']} focused on {', '.join(config['services'][:-1])} and {config['services'][-1]}.",
                f"{config['org_name']} is the {config['org_type']} I represent. We specialize in {', '.join(config['services'])}."
            ],
            'patterns': [],
            'triggers': [
                f"what is {config['org_name'].lower()}",
                f"about {config['org_name'].lower()}",
                f"tell me about {config['org_name'].lower()}"
            ]
        },
        {
            'question': f"What does {config['org_name']} do?",
            'responses': [
                f"At {config['org_name']}, we work on {', '.join(config['services'][:-1])} and {config['services'][-1]}. I'm proud to be part of this team!",
                f"Our {config['org_type']} focuses on {', '.join(config['services'])}. As a representative, I can tell you more about our work."
            ],
            'patterns': [],
            'triggers': [
                f"what does {config['org_name'].lower()} do",
                f"work of {config['org_name'].lower()}",
                f"services of {config['org_name'].lower()}",
                f"what your {config['org_type']} does"
            ]
        }
    ]
    
    return knowledge_base + org_questions

# -------------------- Response Generation --------------------
def search_knowledge(query, knowledge_base, config):
    """Search knowledge base with multiple matching strategies"""
    query = query.lower()
    
    # 1. Check trigger phrases
    for entry in knowledge_base:
        for trigger in entry.get('triggers', []):
            if trigger in query:
                return random.choice(entry['responses'])
    
    # 2. Check keyword patterns
    for entry in knowledge_base:
        for pattern in entry['patterns']:
            if pattern.search(query):
                return random.choice(entry['responses'])
    
    # 3. Fuzzy match questions
    best_score = 0
    best_entry = None
    for entry in knowledge_base:
        score = fuzz.ratio(query, entry['question'].lower())
        if score > best_score and score > 70:
            best_score = score
            best_entry = entry
    
    return random.choice(best_entry['responses']) if best_entry else None

def search_website_content(query, website_index, config):
    """Search crawled website content"""
    query = query.lower()
    query_words = set(query.split())
    
    best_match = None
    best_score = 0
    
    for url, data in website_index.items():
        content = f"{data['title']} {data['text']}".lower()
        content_words = set(content.split())
        
        # Score based on keyword matches
        common_words = query_words & content_words
        score = len(common_words)
        
        # Boost for title matches
        title_words = set(data['title'].lower().split())
        title_matches = len(query_words & title_words)
        score += title_matches * 2
        
        if score > best_score:
            best_score = score
            best_match = (url, data)
    
    if best_score >= 2:  # Minimum threshold
        url, data = best_match
        sentences = nltk.sent_tokenize(data['text'])
        best_sentence = max(sentences, 
                          key=lambda s: len(set(s.lower().split()) & query_words),
                          default="")
        
        if best_sentence:
            return f"From our website: {best_sentence.strip()} [Learn more at {url}]"
    
    return None

def handle_general_conversation(query):
    """Handle common conversational patterns"""
    query = query.lower()
    
    # Greetings
    greetings = ["hi", "hello", "hey"]
    if any(g in query for g in greetings):
        return random.choice([
            "Hello! How can I assist you today?",
            "Hi there! What can I do for you?"
        ])
    
    # How are you
    if "how are you" in query:
        return random.choice([
            "I'm doing well, thank you for asking!",
            "I'm great! How about you?"
        ])
    
    # Thanks
    if "thank" in query:
        return random.choice([
            "You're welcome!",
            "Happy to help!"
        ])
    
    # Time
    if "time" in query:
        return f"The current time is {datetime.now().strftime('%H:%M')}."
    
    return None

# -------------------- Gemini Integration --------------------
def get_gemini_response(query, config, website_index, knowledge_base):
    """Generate response using Gemini with organization context"""
    try:
        # Prepare context from knowledge base
        context = f"{config['org_name']} Knowledge Base:\n"
        for entry in knowledge_base:
            context += f"Q: {entry['question']}\nA: {entry['responses'][0]}\n\n"
        
        # Add website context
        context += f"\nWebsite Content Summary:\n"
        for url, data in list(website_index.items())[:3]:  # Use first 3 pages
            context += f"Page: {data['title']}\nKey Info: {data['text'][:200]}...\n\n"
        
        # Add organization identity
        context += f"""
        My Identity:
        - I am {config['name']}, the {config['org_name']} assistant
        - Our {config['org_type']} focuses on: {', '.join(config['services'])}
        - Founded by: {config['founder']}
        - Website: {config['website']}
        """
        
        prompt = f"""You are {config['name']}, the official assistant for {config['org_name']}.
        Strict Rules:
        1. Always respond as if you're part of the organization
        2. Use "we" and "our" when referring to the organization
        3. For unknown topics, direct to {config['website']}
        4. Keep responses under 3 sentences
        
        Context: {context}
        
        User Query: {query}
        
        Response:"""
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        logging.error(f"Gemini error: {str(e)}")
        return f"I'm having trouble accessing that information. Please visit {config['website']} for details."

# -------------------- Chatbot Handlers --------------------
def get_org_response(query, config):
    """Generate response for organization-specific queries"""
    # Load knowledge and content
    knowledge_base = load_knowledge_base(config)
    website_index = load_json_file(os.path.join(json_dir, config['content_file']))
    
    # 1. Handle identity questions
    identity_phrases = [
        "who are you",
        "your name",
        "what do you do",
        "your role"
    ]
    if any(phrase in query.lower() for phrase in identity_phrases):
        return f"I'm {config['name']}, the digital assistant for {config['org_name']}. I can tell you about our work in {', '.join(config['services'])}."
    
    # 2. Handle general conversation
    general_response = handle_general_conversation(query)
    if general_response:
        return general_response
    
    # 3. Check knowledge base
    kb_response = search_knowledge(query, knowledge_base, config)
    if kb_response:
        return kb_response
    
    # 4. Search website content
    web_response = search_website_content(query, website_index, config)
    if web_response:
        return web_response
    
    # 5. Fallback to Gemini
    return get_gemini_response(query, config, website_index, knowledge_base)

# -------------------- API Endpoints --------------------
@csrf_exempt
def get_indeed_response(request):
    """Django view function for Indeed chatbot API"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('prompt', '').strip()
            
            if not user_message:
                return JsonResponse({'text': 'Please provide a message'}, status=400)
            
            # Get the response using the internal function
            bot_response = get_org_response(user_message, INDEED_CONFIG)
            
            return JsonResponse({'text': bot_response})
            
        except json.JSONDecodeError:
            return JsonResponse({'text': 'Invalid JSON data'}, status=400)
        except Exception as e:
            logging.error(f"Indeed chatbot error: {str(e)}")
            return JsonResponse({'text': 'Sorry, something went wrong'}, status=500)
    
    return JsonResponse({'text': 'Only POST requests are supported'}, status=405)

@csrf_exempt
def get_gmtt_response(request):
    """Django view function for GMTT chatbot API"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('prompt', '').strip()
            
            if not user_message:
                return JsonResponse({'text': 'Please provide a message'}, status=400)
            
            # Get the response using the internal function
            bot_response = get_org_response(user_message, GMTT_CONFIG)
            
            return JsonResponse({'text': bot_response})
            
        except json.JSONDecodeError:
            return JsonResponse({'text': 'Invalid JSON data'}, status=400)
        except Exception as e:
            logging.error(f"GMTT chatbot error: {str(e)}")
            return JsonResponse({'text': 'Sorry, something went wrong'}, status=500)
    
    return JsonResponse({'text': 'Only POST requests are supported'}, status=405)

# -------------------- Background Services --------------------
def refresh_content():
    """Periodically refresh website content"""
    while True:
        logging.info("Refreshing website content...")
        crawl_and_save_website(INDEED_CONFIG['website'], INDEED_CONFIG)
        crawl_and_save_website(GMTT_CONFIG['website'], GMTT_CONFIG)
        time.sleep(86400)  # Refresh daily

# Start background thread
threading.Thread(target=refresh_content, daemon=True).start()

# Initial content load
if not os.path.exists(os.path.join(json_dir, INDEED_CONFIG['content_file'])):
    crawl_and_save_website(INDEED_CONFIG['website'], INDEED_CONFIG)

if not os.path.exists(os.path.join(json_dir, GMTT_CONFIG['content_file'])):
    crawl_and_save_website(GMTT_CONFIG['website'], GMTT_CONFIG)