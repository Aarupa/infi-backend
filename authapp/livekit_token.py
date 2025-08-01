# authapp/livekit_token.py

import jwt
import time

LIVEKIT_API_KEY = "your_api_key"
LIVEKIT_SECRET_KEY = "your_secret_key"
LIVEKIT_TTL = 3600  # seconds

def generate_livekit_token(identity, room="default-room"):
    now = int(time.time())

    payload = {
        "iss": LIVEKIT_API_KEY,
        "sub": identity,
        "iat": now,
        "exp": now + LIVEKIT_TTL,
        "video": {
            "roomJoin": True,
            "room": room,
        }
    }

    return jwt.encode(payload, LIVEKIT_SECRET_KEY, algorithm="HS256")
