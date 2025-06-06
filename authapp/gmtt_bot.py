from .common_utils import *
import google.generativeai as genai
from urllib.parse import urljoin
from .website_scraper import build_website_guide
from .website_guide import get_website_guide_response
import os

# Gemini API configuration
genai.configure(api_key="AIzaSyA4bFTPKOQ3O4iKLmvQgys_ZjH_J1MnTUs")

GMTT_NAME = "Infi"
GMTT_INDEX = {}


# Build absolute paths to JSON files
current_dir = os.path.dirname(__file__)
json_dir = os.path.join(current_dir, "json_files")

greetings_path = os.path.join(json_dir, "greetings.json")
farewells_path = os.path.join(json_dir, "farewells.json")
general_path = os.path.join(json_dir, "general.json")
trees_path = os.path.join(json_dir, "trees.json")

# Load knowledge bases globally once
greetings_kb = load_json_data(greetings_path).get("greetings", {})
farewells_kb = load_json_data(farewells_path).get("farewells", {})
general_kb = load_json_data(general_path).get("general", {})
gmtt_kb = load_knowledge_base(trees_path)

# def crawl_gmtt_website():
#     global GMTT_INDEX
#     GMTT_INDEX = crawl_website("https://www.givemetrees.org", max_pages=30)
#     print(f"[INFO] Crawled {len(GMTT_INDEX)} pages from givemetrees.org")
#     return GMTT_INDEX

# GMTT_INDEX = crawl_gmtt_website()

def get_gemini_gmtt_response(user_query):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        match = find_matching_content(user_query, GMTT_INDEX, threshold=0.6)

        context = """
        Give Me Trees Foundation is a non-profit organization dedicated to environmental conservation.
        Key Information:
        - Founded in 1978 by Kuldeep Bharti
        - Headquarters in New Delhi, India
        - Planted over 20 million trees
        - Focus areas: Urban greening, rural afforestation, environmental education
        - Website: https://www.givemetrees.org
        """

        if match:
            context += f"\n\nRelevant page content from {match['title']}:\n{match['text']}"
            print(f"[DEBUG] Matched page title: {match['title']}")
            print(f"[DEBUG] Matched page snippet:\n{match['text'][:500]}")  # print 


        prompt = f"""You are an assistant for Give Me Trees Foundation. and developed by indeed inspiring infotech AIML team.
Rules:
1. Only provide information about Give Me Trees Foundation from the website givemetrees.org 
2. Also handle general greetings, farewells, and general conversations like hi, hello, how are you, etc.
3. For other topics, respond "I specialize in tree-related questions."
4. Keep responses under 3 sentences.
5. If needed, mention to visit givemetrees.org for more details.

Context: {context}

Query: {user_query}

Response:"""

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        logging.error(f"Gemini API error: {str(e)}")
        return "I'm having trouble accessing tree information right now. Please visit givemetrees.org for details."

def get_gmtt_response(user_input):
    if "what is your name" in user_input.lower() or "your name" in user_input.lower():
        return f"My name is {GMTT_NAME}. I'm here to help with Give Me Trees Foundation queries."

     # if response := handle_greetings(user_input, greetings_kb):
    #     print("[INFO] Response from: Greetings")
    #     return response
    
    # if response := handle_farewells(user_input, farewells_kb):
    #     print("[INFO] Response from: Farewells")
    #     return response
    
    # if response := handle_general(user_input, general_kb):
    #     print("[INFO] Response from: General")
    #     return response

    if response := search_knowledge(user_input, gmtt_kb):
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

    if guide_response := get_website_guide_response(user_input, "givemetrees.org", "https://www.givemetrees.org"):
        print("[INFO] Response from: Website Guide")
        return f"I found this relevant page about trees: {guide_response}"
    
    print("[INFO] Response from: Gemini API")
    return get_gemini_gmtt_response(user_input)
