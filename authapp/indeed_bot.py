from .common_utils import *
import google.generativeai as genai
from urllib.parse import urljoin
from .website_scraper import build_website_guide
from .website_guide import get_website_guide_response
import os
import language_tool_python

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

# Load knowledge bases globally once
greetings_kb = load_json_data(greetings_path).get("greetings", {})
farewells_kb = load_json_data(farewells_path).get("farewells", {})
general_kb = load_json_data(general_path).get("general", {})
indeed_kb = load_knowledge_base(content_path)

# def crawl_indeed_website():
#     global INDEED_INDEX
#     INDEED_INDEX = crawl_website("https://indeedinspiring.com/", max_pages=30)
#     print(f"[INFO] Crawled {len(INDEED_INDEX)} pages from indeedinspiring.com")
#     return INDEED_INDEX

# INDEED_INDEX = crawl_indeed_website()

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
            print(f"[DEBUG] Matched page snippet:\n{match['text'][:500]}")  #

        prompt = f"""You are a assistant for Indeed Inspiring Infotech and developed by indeed inspiring infotech AIML team.
Strict Rules:
1. Only provide information about Indeed Inspiring Infotech from the website indeedinspiring.com
2. also handle general greetings and farewells and general conversations like hi, hello, how are you, etc.
3. For other topics, politely apologize and respond: "Sorry, I can only assist with Indeed Inspiring Infotech related questions."
4. Keep responses concise (1 sentence maximum)
5. if needed mention to visit indeedinspiring.com for more details

Context: {context}

User Query: {user_query}

Response:"""
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return "I'm having trouble accessing company information right now. Please visit indeedinspiring.com for details."

grammar_tool = language_tool_python.LanguageTool('en-US')

def is_grammatically_correct(sentence):
    matches = grammar_tool.check(sentence)
    # If there are no grammar errors, return True
    return len(matches) == 0

def get_indeed_response(user_input):
    # Check grammar first
    if not is_grammatically_correct(user_input):
        return "Please enter a grammatically correct sentence."

    # Simple keyword checks and KB lookups
    if "what is your name" in user_input.lower() or "your name" in user_input.lower():
        print("[INFO] Response from: Name handler")
        return f"My name is {CHATBOT_NAME}. How can I assist you with Indeed Inspiring Infotech?"

    # if response := handle_greetings(user_input, greetings_kb):
    #     print("[INFO] Response from: Greetings")
    #     return response
    
    # if response := handle_farewells(user_input, farewells_kb):
    #     print("[INFO] Response from: Farewells")
    #     return response
    
    # if response := handle_general(user_input, general_kb):
    #     print("[INFO] Response from: General")
    #     return response

    if response := search_knowledge(user_input, indeed_kb):
        print("[INFO] Response from: Knowledge Base")
        return response
    
    if response := handle_time_based_greeting(user_input):
        print("[INFO] Response from: Time-Based Greeting")
        return response
        
    if response := handle_date_related_queries(user_input):
        print("[INFO] Response from: Date Handler")
        return response
    
    if response := generate_nlp_response(user_input):
        print("[INFO] Response from: NLP Generator")
        return response

    if response := get_website_guide_response(user_input, "indeedinspiring.com", "https://indeedinspiring.com"):
        print("[INFO] Response from: Website Guide")
        return f"I found this relevant page for you: {response}"

    print("[INFO] Response from: Gemini API")
    return get_gemini_indeed_response(user_input)
