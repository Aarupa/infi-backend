from .common_utils import *
import google.generativeai as genai
from urllib.parse import urljoin


# Gemini API configuration
genai.configure(api_key="AIzaSyA4bFTPKOQ3O4iKLmvQgys_ZjH_J1MnTUs")

CHATBOT_NAME = "Infi"
INDEED_INDEX = {}

def crawl_indeed_website():
    return crawl_website("https://indeedinspiring.com")

def get_gemini_indeed_response(user_query):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
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
        - Founded by Kushal Sharma
        - Specializes in AI, web development, and digital transformation
        - Website: https://indeedinspiring.com
        """
        
        if best_match and best_score > 2:
            context += f"\n\nRelevant page content from {best_match['title']}:\n{best_match['text'][:2000]}..."
        
        prompt = f"""You are a specialist assistant for Indeed Inspiring Infotech.
        Strict Rules:
        1. Only provide information about Indeed Inspiring Infotech and its services
        2. For other topics, respond "I specialize in Indeed Inspiring Infotech related questions"
        3. Keep responses concise (1 sentences maximum)
        4. Always mention to visit indeedinspiring.com for more details
        
        Context: {context}
        
        User Query: {user_query}
        
        Response:"""
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return "I'm having trouble accessing company information right now. Please visit indeedinspiring.com for details."

def get_indeed_response(user_input, indeed_kb):
    if "what is your name" in user_input.lower() or "your name" in user_input.lower():
        return f"My name is {CHATBOT_NAME}. How can I assist you with Indeed Inspiring Infotech?"
    
    kb_response = search_knowledge(user_input, indeed_kb)
    if kb_response:
        return kb_response
    
    general_response = generate_nlp_response(user_input, CHATBOT_NAME)
    if general_response:
        return general_response
    
    time_response = handle_time_based_greeting(user_input)
    if time_response:
        return time_response
        
    date_response = handle_date_related_queries(user_input)
    if date_response:
        return date_response
    
    return get_gemini_indeed_response(user_input)