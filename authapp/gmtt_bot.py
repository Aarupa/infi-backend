
# gmtt_bot.py

# Question and Answer list
qa_data = {
    "what is the sant nirankari mission": "The Sant Nirankari Mission is a spiritual organization founded in 1929 that aims to promote universal brotherhood and peace by helping people realize God through the guidance of a living Satguru.",
    "what is the main message of the sant nirankari mission": "The mission teaches that God is formless and omnipresent, and every human being can experience God-realisation in their lifetime through the Satguru’s grace. Its core values are love, humility, unity, and service.",
    "who is the current spiritual head of the mission": "As of now, the spiritual head is Satguru Mata Sudiksha Ji Maharaj, who is leading the mission with a focus on youth empowerment, devotion, and social welfare.",
    "what is meant by god-realisation in this mission": "God-Realisation means experiencing and becoming aware of the formless God (Nirankar) within and around us. This is made possible by the Satguru during a spiritual revelation (Gyan).",
    "what is the role of the satguru in the sant nirankari mission": "The Satguru is the enlightened master who grants God-knowledge and guides followers on how to live a truthful and spiritual life filled with love, service, and devotion.",
    "what are the key practices of the mission": "The mission emphasizes three main practices:\n• Sewa (selfless service)\n• Simran (constant remembrance of Nirankar)\n• Satsang (attending spiritual gatherings for growth and unity)",
    "does the sant nirankari mission follow a particular religion": "No. The mission respects all religions and does not promote conversion. It focuses on spirituality and humanity, encouraging people of all backgrounds to come together in peace.",
    "what is the purpose of satsang in the mission": "Satsang is a spiritual congregation where followers come together to listen to discourses, sing devotional hymns, and strengthen their connection with God and one another.",
    "what social work does the mission do": "The mission organizes blood donation drives, tree plantation, cleanliness campaigns, disaster relief, health camps, and youth development programs as part of its 'Manav Sewa is Madhav Sewa' belief (serving humanity is serving God).",
    "what does nirankar mean": "“Nirankar” means formless God—the eternal, omnipresent divine power that cannot be seen with physical eyes but can be experienced through divine knowledge (Brahmgyan) granted by the Satguru.",
    "what is brahmgyan": "Brahmgyan is the realisation of the formless God that is given directly by the Satguru. It is not theoretical, but a practical experience that changes one’s vision of life and brings peace, clarity, and spiritual awakening.",
    "how does the mission help in day-to-day life": "The teachings help individuals to live a peaceful, ego-free, and balanced life. They encourage forgiveness, self-discipline, positive thinking, and service to others, which improves personal and social life.",
    "what role do youth play in the mission": "Youth are seen as the future of the Mission and society. Special platforms like Nirankari Youth Symposiums, Sewadal Training, and Yuvak Mandals are organized to engage youth in spirituality, leadership, and service.",
    "what is nirankari sewadal": "Nirankari Sewadal is the volunteer wing of the Mission, known for discipline, humility, and service. Members offer selfless service in organizing events, maintaining order, and social welfare activities.",
    "what is the nirankari sant samagam": "It is the largest annual spiritual congregation of the Mission, where lakhs of devotees from India and abroad gather to share spiritual thoughts, devotional music, and collective experiences of unity and service.",
    "how can someone join the sant nirankari mission": "Anyone can join by attending Satsang gatherings, meeting a Gyan Pracharak, and receiving Brahmgyan from the Satguru’s representative. There is no conversion, and all are welcomed with love.",
    "does the mission encourage education and careers": "Absolutely. The Mission believes in balancing spiritual and worldly responsibilities. It encourages followers to study, work honestly, and succeed in life while staying grounded in values.",
    "what is the sant nirankari charitable foundation": "It is the social welfare wing of the Mission, focused on health, education, environment, and humanitarian aid—carrying out blood donation camps, cleanliness drives, relief work, and more."
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

# To remember if it's the user's first interaction (use a dictionary or database in production)
session_memory = {}

def get_gmtt_response(user_input, user=None):
    user_input = user_input.strip().lower()

    # Show intro only once per session/user
    if user and user.username not in session_memory:
        session_memory[user.username] = True
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
