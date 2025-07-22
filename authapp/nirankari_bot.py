# nirankari_bot.py

# Question and Answer list
qa_data = {
    "what is sant nirankari mission": "Sant Nirankari Mission is a spiritual organization focused on God-realisation and human unity.",
    "who is the current guru": "The current Satguru is Mata Sudiksha Ji Maharaj.",
    "what is brahmgyan": "Brahmgyan means realisation of formless God (Nirankar) through the grace of the Satguru.",
    "what is sewa": "Sewa means selfless service — one of the core principles of the Mission.",
    "what is satsang": "Satsang is a spiritual gathering where devotees come together to remember Nirankar and learn from each other.",
    "what is simran": "Simran means constant remembrance of Nirankar through repetition and devotion.",
    "what is nirankar": "Nirankar means formless God — the eternal, omnipresent divine power.",
    "what is the purpose of the mission": "To unite humanity as one family by spreading God-realisation and selfless love.",
    "do you follow any religion": "The Mission respects all religions and doesn’t ask anyone to convert.",
    "what is the role of youth": "Youth play a vital role in spreading the message of love, unity and service through Yuvak Mandals and various platforms."
}

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

# Bot function
def get_nirankari_response(user_input, is_first_message=False):
    user_input = user_input.strip().lower()

    if is_first_message:
        return intro_message

    if user_input in ["bye", "exit", "thank you", "thanks"]:
        return farewell_message

    for question, answer in qa_data.items():
        if question in user_input:
            return answer

    return "I'm sorry, I couldn't understand that. Please ask something related to the Sant Nirankari Mission."
