from .common_utils import *
import google.generativeai as genai
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import requests
import logging

# Gemini API configuration
genai.configure(api_key="AIzaSyA4bFTPKOQ3O4iKLmvQgys_ZjH_J1MnTUs")

GMTT_NAME = "Infi"
GMTT_INDEX = {}

def crawl_gmtt_website():
    return crawl_website("https://www.givemetrees.org")

def get_gemini_gmtt_response(user_query):
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
        Give Me Trees Foundation is a non-profit organization dedicated to environmental conservation.
        Key Information:
        - Founded in 1978 by Kuldeep Bharti
        - Headquarters in New Delhi, India
        - Planted over 20 million trees
        - Focus areas: Urban greening, rural afforestation, environmental education
        - Website: https://www.givemetrees.org
        """
        
        if best_match and best_score > 2:
            context += f"\n\nRelevant page content from {best_match['title']}:\n{best_match['text'][:2000]}..."
        
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

def get_gmtt_response(user_input, gmtt_kb):
    if "what is your name" in user_input.lower() or "your name" in user_input.lower():
        return f"My name is {GMTT_NAME}. I'm here to help with Give Me Trees Foundation queries."
    
    kb_response = search_knowledge(user_input, gmtt_kb)
    if kb_response:
        return kb_response
    
    general_response = generate_nlp_response(user_input, GMTT_NAME)
    if general_response:
        return general_response
    
    time_response = handle_time_based_greeting(user_input)
    if time_response:
        return time_response
        
    date_response = handle_date_related_queries(user_input)
    if date_response:
        return date_response
    
    tree_keywords = ["tree", "plant", "forest", "environment", "gmtt", "give me trees"]
    if not any(keyword in user_input.lower() for keyword in tree_keywords):
        return f"I'm {GMTT_NAME}, the Give Me Trees specialist. How can I help you with tree planting today?"
    
    return get_gemini_gmtt_response(user_input)