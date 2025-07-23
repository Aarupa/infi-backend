
# nirankari_bot.py

# Question and Answer list
from .QA import qa_data

# Intro message (once at start)
intro_message = (
    "Dhan Nirankar Ji!\n"
    "Welcome! I am a spiritual assistant designed to share the divine teachings of the Sant Nirankari Mission.\n"
    "In this mission, the Satguru talks about God-realisation, or how to live a life of love, peace, and unity.\n\n"
    "Let’s begin this journey of truth and spirituality together.\n"
    "What would you like to know?"
)

# Farewell message (on goodbye)
farewell_message = (
    "🙏 Dhan Nirankar Ji! 🙏\n"
    "Thank you for sharing this spiritual moment with me.\n"
    "Let us always walk the path of truth, love, humility, and selfless service.\n"
    "May Nirankar bless you and your family with peace, wisdom, and devotion.\n\n"
    "🕊️ Always remember – We are all one, connected through the same formless God. 🙏"
)

# To remember if it's the user's first interaction (use a dictionary or database in production)
session_memory = {}

def get_nirankari_response(user_input, user=None):
    user_input = user_input.strip().lower()
    print(f"[INFO] User: {user}, Input: {user_input}")

    # Show intro only once per session/user
    if user and user not in session_memory:
        session_memory[user] = True
        return intro_message

    if user_input in ["bye", "exit", "thank you", "thanks"]:
        return farewell_message

    for question, answer in qa_data.items():
        if question in user_input:
            return answer

    return (
        "I'm sorry, I couldn't understand that.\n"
        "Please ask something related to the Sant Nirankari Mission."
    )
