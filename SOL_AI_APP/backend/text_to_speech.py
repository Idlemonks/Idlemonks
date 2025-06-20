import os
from elevenlabs import generate, play, set_api_key
from dotenv import load_dotenv

load_dotenv()
set_api_key(os.getenv("ELEVEN_API_KEY"))

def speak_text(text: str) -> bytes:
    return generate(text=text, voice="Rachel")
