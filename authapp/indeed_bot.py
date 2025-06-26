from .common_utils import *
import google.generativeai as genai
from urllib.parse import urljoin
from .website_scraper import build_website_guide
from .website_guide import get_website_guide_response
import os
import json
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
history_file_path = os.path.join(json_dir, "session_history.json")

# Ensure history file exists
if not os.path.exists(history_file_path):
    with open(history_file_path, "w") as f:
        json.dump([], f)

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
3. For unrelated topics, reply that you don’t have info on that and focus only on Indeed Inspiring Infotech. Include the topic name in your response. Rephrase each time.
4. Keep responses concise (1 sentence maximum)
5. if needed mention to visit indeedinspiring.com for more details

Context: {context}

User Query: {user_query}

Response:"""
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return "I'm having trouble accessing company information right now. Please visit indeedinspiring.com for details."

def update_and_respond_with_history(user_input, current_response):
    exit_keywords = ["bye", "bye bye", "exit"]
    history = load_session_history(history_file_path)

    if any(kw in user_input.lower() for kw in exit_keywords):
        # Clear history file on session end
        open(history_file_path, "w").close()
        return current_response


    history_text = ""
    for turn in history:
        history_text += f"User: {turn['user']}\nBot: {turn['bot']}\n"

    prompt = f"""
        You are a smart assistant representing Indeed Inspiring Infotech.
        Using the conversation history below and the current system reply, generate a concise, coherent response that may incorporate context from history if relevant.

        Rules:
        - If the user has asked a similar or identical question earlier in Conversation History below then, start your reply with a phrase not exact but similar to "As I mentioned earlier," and rephrase and slightly expand the original response.
        - Ensure the response is natural, contextual, and varies in tone. Avoid sounding repetitive or robotic.

        Conversation History:
        {history_text}

        Current System Response:
        {current_response}

        Final Answer (Keep it natural, relevant, and concise. Vary length based on question complexity):
        """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        final_response = model.generate_content(prompt)
        history.append({"user": user_input, "bot": final_response.text.strip()})
        save_session_history(history_file_path, history)
        return final_response.text.strip()
    except Exception:
        history.append({"user": user_input, "bot": current_response})
        save_session_history(history_file_path, history)
        return current_response

def get_indeed_response(user_input):
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

    # if response := search_knowledge(user_input, indeed_kb):
    #     print("[INFO] Response from: Knowledge Base")
    #     return response
    
    # if response := handle_time_based_greeting(user_input):
    #     print("[INFO] Response from: Time-Based Greeting")
    #     return response
        
    # if response := handle_date_related_queries(user_input):
    #     print("[INFO] Response from: Date Handler")
    #     return response
    
    # if response := generate_nlp_response(user_input):
    #     print("[INFO] Response from: NLP Generator")
    #     return response

    # # if response := get_website_guide_response(user_input, "indeedinspiring.com", "https://indeedinspiring.com"):
    # #     print("[INFO] Response from: Website Guide")
    # #     return f"I found this relevant page for you: {response}"

    # print("[INFO] Response from: Gemini API")
    # return get_gemini_indeed_response(user_input)
    if response := search_knowledge(user_input, indeed_kb):
        print("[INFO] Response from: Knowledge Base")
        return update_and_respond_with_history(user_input, response)

    if response := handle_time_based_greeting(user_input):
        print("[INFO] Response from: Time-Based Greeting")
        return update_and_respond_with_history(user_input, response)

    if response := handle_date_related_queries(user_input):
        print("[INFO] Response from: Date Handler")
        return update_and_respond_with_history(user_input, response)

    if response := generate_nlp_response(user_input):
        print("[INFO] Response from: NLP Generator")
        return update_and_respond_with_history(user_input, response)

    # Uncomment if website guide used
    # if response := get_website_guide_response(user_input, "indeedinspiring.com", "https://indeedinspiring.com"):
    #     print("[INFO] Response from: Website Guide")
    #     return update_and_respond_with_history(user_input, f"I found this relevant page for you: {response}")

    print("[INFO] Response from: Gemini API")
    response = get_gemini_indeed_response(user_input)
    return update_and_respond_with_history(user_input, response)
