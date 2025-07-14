import json
import os
import requests


def get_smart_keywords(user_query):
    """Use Mistral to extract semantically relevant keywords from a query."""
    prompt = f"""
Extract 10 semantically meaningful keywords or keyphrases from the following user query.
Avoid stopwords, and focus on user intent. Return only a Python list of strings.

Query: "{user_query}"
"""
    text = call_mistral_model(prompt, max_tokens=100).strip()

    if text.startswith("```"):
        text = text.strip("` \n")
        if "\n" in text:
            text = "\n".join(text.split("\n")[1:])

    try:
        keywords = eval(text)
        return [k.lower() for k in keywords if isinstance(k, str)]
    except Exception as e:
        print("Failed to parse keywords:", e)
        return []

def load_sections(jsonl_path):
    """Load all JSONL entries as list of dicts."""
    with open(jsonl_path, "r", encoding="utf-8") as f:
        return [json.loads(line.strip()) for line in f]

def match_sections(keywords, sections):
    """Find sections that contain any of the keywords."""
    matched = []
    for section in sections:
        text = section.get("text", "").lower()
        if any(kw in text for kw in keywords):
            matched.append(section)
    return matched

def query_best_link(user_query, matched_sections):
    """Use Mistral to select the most relevant link from matched sections."""
    context = "\n\n".join(
        f"Section Title: {s['section_title']}\nText: {s['text']}\nURL: {s['url']}"
        for s in matched_sections
    )

    prompt = f"""
You're a helpful assistant. A user has a question, and below are content sections scraped from a website.

Based on their query and the content, return only the single most relevant URL. Do NOT explain.

User Query: "{user_query}"

Sections:
{context}

Output ONLY the best-matching URL.
"""

    return call_mistral_model(prompt, max_tokens=100).strip()

def get_website_guide_response(user_query, website_domain, website_url=None):
    print("i am here for any link")
    """Main function to get guided response for a website query"""
    jsonl_path = f"{website_domain}_guide.jsonl"
    # print(f"[DEBUG] Looking for guide file at: {os.path.abspath(jsonl_path)}")
    
    # Build guide if it doesn't exist and website_url is provided
    if not os.path.exists(jsonl_path) and website_url:
        print("hii")
        from .website_scraper import build_website_guide
        build_website_guide(website_url)
    
    if not os.path.exists(jsonl_path):
        return None
    
    keywords = get_smart_keywords(user_query)
    if not keywords:
        return None

    sections = load_sections(jsonl_path)
    matched_sections = match_sections(keywords, sections)

    if not matched_sections:
        return None

    best_link = query_best_link(user_query, matched_sections)
    return best_link

MISTRAL_API_KEY = "5jMPffjLAwLyyuj6ZwFHhbLZxb2TyfUR"

def call_mistral_model(prompt, max_tokens=200):
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-small",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content'].strip()
    else:
        print(f"[ERROR] Mistral API failed: {response.status_code} {response.text}")
        return ""