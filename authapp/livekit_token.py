# authapp/livekit_token.py

import jwt
import time

LIVEKIT_API_KEY = "APIsfZahc2yXTnS"
LIVEKIT_SECRET_KEY = "VhIOTlpe4zdPooW8nDDeDVn79Tem8l8O2jnvf84Lv8kD"
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

    token = jwt.encode(payload, LIVEKIT_SECRET_KEY, algorithm="HS256")

    # Fix: decode bytes to string (if needed)
    if isinstance(token, bytes):
        token = token.decode('utf-8')

    return token
