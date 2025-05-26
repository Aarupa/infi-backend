import os
import json
import re
import random
import string
from datetime import datetime, timedelta
from fuzzywuzzy import fuzz, process
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import spacy
import nltk

# Initialize NLP and sentiment analysis
nlp = spacy.load("en_core_web_sm")
nltk.download('wordnet')
sentiment_analyzer = SentimentIntensityAnalyzer()

# -------------------- Shared Utility Functions --------------------
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

def handle_time_based_greeting(msg):
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

import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def crawl_website(base_url, max_pages=10):
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


def generate_nlp_response(msg, bot_name):
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