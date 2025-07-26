import os
import json
import numpy as np
import re
from sentence_transformers import SentenceTransformer, util
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load your QA.json
with open(os.path.join(BASE_DIR, 'QA.json'), 'r', encoding='utf-8') as f:
    qa_data = json.load(f)

# Load sentence-transformers multilingual model
model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')

# Path to cache embeddings
EMBEDDING_CACHE_PATH = os.path.join(BASE_DIR, 'qa_embeddings.npy')

intro_message_en = (
    " Dhan Nirankar Ji! \n"
    "How may I assist you today?"
)

intro_message_hi = (
    " धन निरंकार जी! \n"
    "स्वागत है। मैं संत निरंकारी मिशन की शिक्षाओं को साझा करने वाला आध्यात्मिक सहायक हूँ।\n"
    "मिशन ईश्वर की अनुभूति और प्रेम, शांति, एकता के साथ जीवन बिताने पर ज़ोर देता है।\n\n"
    "मैं आपकी किस प्रकार सहायता कर सकता हूँ?"
)

farewell_message_en = (
    " Dhan Nirankar Ji! \n"
    "Thank you for this spiritual moment.\n"
    "May Nirankar bless you with peace, wisdom, and devotion.\n\n"
    "Remember, we are all one through the formless God. "
)

farewell_message_hi = (
    "धन निरंकार जी! \n"
    "इस आध्यात्मिक क्षण के लिए धन्यवाद।\n"
    "निरंकार आपको शांति, ज्ञान और भक्ति से आशीर्वादित करें।\n\n"
    "याद रखें, हम सभी निराकार ईश्वर के माध्यम से एक हैं। "
)

session_memory = {}

GREETING_PATTERNS = [
    r"\bhello\b", r"\bhi\b", r"\bhey\b", r"\bgood\s(morning|afternoon|evening)\b",
    r"\bgreetings\b", r"\bwhat's up\b", r"\bhow are you\b",
    r"\bनमस्ते\b", r"\bनमस्कार\b", r"\bसत श्री अकाल\b", r"\bप्रणाम\b"
]

FAREWELL_PATTERNS = [
    r"\bbye\b", r"\bgoodbye\b", r"\bsee you\b", r"\bexit\b",
    r"\bthank(s| you)\b", r"\bfarewell\b", r"\btake care\b",
    r"\bअलविदा\b", r"\bफिर मिलेंगे\b", r"\bधन्यवाद\b", r"\bशुभकामनाएँ\b"
]

HINDI_RESPONSE_KEYWORDS = [
    r"\breply\s+in\s+hindi\b",
    r"\banswer\s+in\s+hindi\b",
    r"\btell\s+in\s+hindi\b",
    r"हिंदी\s+में\s+जवाब",
    r"हिंदी\s+में\s+उत्तर",
    r"हिंदी\s+में\s+जवाब\s+दो",
    r"please\s+respond\s+in\s+hindi"
]

ENGLISH_RESPONSE_KEYWORDS = [
    r"\breply\s+in\s+english\b",
    r"\banswer\s+in\s+english\b",
    r"english\s+में\s+जवाब",
    r"english\s+में\s+उत्तर",
    r"english\s+में\s+जवाब\s+दो",
    r"please\s+respond\s+in\s+english"
]

def contains_hindi(text):
    return bool(re.search('[\u0900-\u097F]', text))

def is_roman_hindi(text):
    return not contains_hindi(text) and bool(re.search(r'[a-zA-Z]', text)) and any(word in text.lower() for word in [
        'kya', 'hai', 'kaun', 'kab', 'kyun', 'kyaha', 'kaise', 'sant', 'sat', 'nirankari', 'bhakti', 'sewa', 'diwas', 'samagam'
    ])

def match_patterns(patterns, text):
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def find_pattern_match(user_input):
    for item in qa_data:
        all_patterns = item.get("en_patterns", []) + item.get("hi_patterns", [])
        for pattern in all_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                return item
    return None

def prepare_qa_embeddings():
    qa_texts = []
    for item in qa_data:
        en_text = " ".join(item.get("en_patterns", []))
        hi_text = " ".join(item.get("hi_patterns", []))
        combined_text = en_text + " " + hi_text
        qa_texts.append(combined_text)
    embeddings = model.encode(qa_texts, convert_to_tensor=False)
    return embeddings

def load_or_compute_embeddings():
    if os.path.exists(EMBEDDING_CACHE_PATH):
        print("[INFO] Loading cached QA embeddings...")
        return np.load(EMBEDDING_CACHE_PATH)
    else:
        print("[INFO] Computing QA embeddings for the first time...")
        embeddings = prepare_qa_embeddings()
        np.save(EMBEDDING_CACHE_PATH, embeddings)
        return embeddings


qa_embeddings = load_or_compute_embeddings()

def semantic_search_answer(user_input, top_k=1, threshold=0.6):
    query_embedding = model.encode([user_input])  # shape: (1, dim)
    similarities = cosine_similarity(query_embedding, qa_embeddings)[0]  # shape: (n,)
    best_index = np.argmax(similarities)
    best_score = similarities[best_index]

    if best_score >= threshold:
        return qa_data[best_index], best_score
    else:
        return None, best_score


def get_nirankari_response(user_input, user=None):
    user_input_clean = user_input.strip()
    print(f"[INFO] User: {user}, Input: {user_input_clean}")
    # -------------------- 2. Check for welcome pattern --------------------
    import re

    WELCOME_RESPONSE = "Hello! Welcome to Nirankari Foundation. I'm your assistant here to guide you through our initiatives and services. How can I help you today?"

    welcome_pattern = r"^(Hello\s[\w@.]+!|Hello!)\sWelcome to Nirankari Foundation\. I'm your assistant here to guide you through our initiatives and services\. How can I help you today\?$"

    if re.match(welcome_pattern, user_input.strip()):
        return WELCOME_RESPONSE


    is_hindi_script = contains_hindi(user_input_clean.lower())
    is_roman = is_roman_hindi(user_input_clean.lower())
    force_hindi = match_patterns(HINDI_RESPONSE_KEYWORDS, user_input_clean.lower())
    force_english = match_patterns(ENGLISH_RESPONSE_KEYWORDS, user_input_clean.lower())

    if force_hindi:
        response_in_hindi = True
    elif force_english:
        response_in_hindi = False
    else:
        if contains_hindi(user_input_clean):
            response_in_hindi = True
        elif is_roman_hindi(user_input_clean):
            response_in_hindi = True
        else:
            response_in_hindi = False  # default to English

    if user and user not in session_memory:
        session_memory[user] = True
        return intro_message_hi if response_in_hindi else intro_message_en

    if match_patterns(GREETING_PATTERNS, user_input_clean.lower()):
        return (
            " धन निरंकार जी! मैं संत निरंकारी मिशन के बारे में आपकी सहायता कैसे कर सकता हूँ?"
            if response_in_hindi else
            "Dhan Nirankar Ji! How can I assist you with the Sant Nirankari Mission today?"
        )

    if match_patterns(FAREWELL_PATTERNS, user_input_clean.lower()):
        return farewell_message_hi if response_in_hindi else farewell_message_en

    matched_qa = find_pattern_match(user_input_clean)
    if matched_qa:
        answer = matched_qa.get("hi_answer" if response_in_hindi else "en_answer")
        if answer:
            return answer

    best_qa, best_score = semantic_search_answer(user_input_clean)

    if best_qa:
        answer = best_qa.get("hi_answer" if response_in_hindi else "en_answer")
        if answer:
            return answer

    # Fallback response if no good match is found
    return (
        "मैं संत निरंकारी मिशन के बारे में आपके प्रश्नों में सहायता करने के लिए यहाँ हूँ।\n"
        "कृपया अपने प्रश्न को पुनः व्यक्त करें या मिशन की शिक्षाओं या सिद्धांतों से संबंधित कुछ पूछें।\n\n"
        if response_in_hindi else
        "I'm here to assist with questions about the Sant Nirankari Mission.\n"
        "Could you please rephrase or ask something related to its teachings or principles?\n\n"
    )
