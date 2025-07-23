import re
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, 'QA.json'), 'r', encoding='utf-8') as f:
    qa_data = json.load(f)

intro_message_en = (
    "🙏 Dhan Nirankar Ji! 🙏\n"
    "Welcome. I am a spiritual assistant here to share the teachings of the Sant Nirankari Mission.\n"
    "The Mission emphasizes God-realisation and living with love, peace, and unity.\n\n"
    "How may I assist you today?"
)

intro_message_hi = (
    "🙏 धन निरंकार जी! 🙏\n"
    "स्वागत है। मैं संत निरंकारी मिशन की शिक्षाओं को साझा करने वाला आध्यात्मिक सहायक हूँ।\n"
    "मिशन ईश्वर की अनुभूति और प्रेम, शांति, एकता के साथ जीवन बिताने पर ज़ोर देता है।\n\n"
    "मैं आपकी किस प्रकार सहायता कर सकता हूँ?"
)

farewell_message_en = (
    "🙏 Dhan Nirankar Ji! 🙏\n"
    "Thank you for this spiritual moment.\n"
    "May Nirankar bless you with peace, wisdom, and devotion.\n\n"
    "Remember, we are all one through the formless God. 🙏"
)

farewell_message_hi = (
    "🙏 धन निरंकार जी! 🙏\n"
    "इस आध्यात्मिक क्षण के लिए धन्यवाद।\n"
    "निरंकार आपको शांति, ज्ञान और भक्ति से आशीर्वादित करें।\n\n"
    "याद रखें, हम सभी निराकार ईश्वर के माध्यम से एक हैं। 🙏"
)

# To remember if it's the user's first interaction
session_memory = {}

# Regex patterns for greeting and farewell detection (both English and Hindi)
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

# Keywords to detect language preference in user input
HINDI_RESPONSE_KEYWORDS = [
    r"\breply\s+in\s+hindi\b",
    r"\banswer\s+in\s+hindi\b",
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
    """Return True if text contains any Hindi character (Unicode range)."""
    return bool(re.search('[\u0900-\u097F]', text))

def match_patterns(patterns, text):
    """Return True if any pattern matches the text."""
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def get_nirankari_response(user_input, user=None):
    user_input_clean = user_input.strip().lower()
    print(f"[INFO] User: {user}, Input: {user_input_clean}")

    # Detect input language
    is_hindi = contains_hindi(user_input)

    # Check language preference in input explicitly
    force_hindi_response = match_patterns(HINDI_RESPONSE_KEYWORDS, user_input_clean)
    force_english_response = match_patterns(ENGLISH_RESPONSE_KEYWORDS, user_input_clean)

    # Decide response language priority
    if force_hindi_response:
        response_in_hindi = True
    elif force_english_response:
        response_in_hindi = False
    else:
        response_in_hindi = is_hindi

    # Show intro only once per session/user
    if user and user not in session_memory:
        session_memory[user] = True
        return intro_message_hi if response_in_hindi else intro_message_en

    # Greeting detection
    if match_patterns(GREETING_PATTERNS, user_input_clean):
        return (
            "🙏 धन निरंकार जी! मैं संत निरंकारी मिशन के बारे में आपकी सहायता कैसे कर सकता हूँ?"
            if response_in_hindi else
            "🙏 Dhan Nirankar Ji! How can I assist you with the Sant Nirankari Mission today?"
        )

    # Farewell detection
    if match_patterns(FAREWELL_PATTERNS, user_input_clean):
        return farewell_message_hi if response_in_hindi else farewell_message_en

    # Iterate through QA pairs to find matching answer
    for qa_item in qa_data:
        # Check Hindi patterns if Hindi response
        if response_in_hindi:
            for pattern in qa_item.get("hi_patterns", []):
                if re.search(pattern, user_input, re.IGNORECASE):
                    return qa_item.get("hi_answer", "")
        else:
            # Check English patterns if English response
            for pattern in qa_item.get("en_patterns", []):
                if re.search(pattern, user_input_clean, re.IGNORECASE):
                    return qa_item.get("en_answer", "")

    # Default fallback response
    return (
        "मैं संत निरंकारी मिशन के बारे में आपके प्रश्नों में सहायता करने के लिए यहाँ हूँ।\n"
        "कृपया अपने प्रश्न को पुनः व्यक्त करें या मिशन की शिक्षाओं या सिद्धांतों से संबंधित कुछ पूछें।\n\n"
        if response_in_hindi else
        "I'm here to assist with questions about the Sant Nirankari Mission.\n"
        "Could you please rephrase or ask something related to its teachings or principles?\n\n"
    )