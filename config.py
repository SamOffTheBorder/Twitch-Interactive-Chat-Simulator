import os
from dotenv import load_dotenv

load_dotenv()

TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL", "")
TWITCH_TOKENS: list[str] = [t.strip() for t in os.getenv("TWITCH_TOKENS", "").split(",") if t.strip()]
TWITCH_ACCESS_TOKEN = TWITCH_TOKENS[0] if TWITCH_TOKENS else ""  # used for Helix API calls (TTS)
TWITCH_STREAMER_TOKEN = os.getenv("TWITCH_STREAMER_TOKEN", "")  # optional: streamer OAuth for private streams
VIEWER_COUNT = len(TWITCH_TOKENS)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free")
OPENROUTER_FALLBACK_MODEL = os.getenv("OPENROUTER_FALLBACK_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/v1")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "")

# Channel points — Client-ID required for all redemptions
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "")
TTS_REWARD_ID = os.getenv("TTS_REWARD_ID", "")            # auto-discovered if blank
HIGHLIGHT_REWARD_ID = os.getenv("HIGHLIGHT_REWARD_ID", "") # auto-discovered if blank
SUB_REWARD_ID = os.getenv("SUB_REWARD_ID", "")            # auto-discovered if blank

# How often TTS fires (seconds). Default: every 3–8 minutes.
TTS_MIN_INTERVAL = int(os.getenv("TTS_MIN_INTERVAL", "180"))
TTS_MAX_INTERVAL = int(os.getenv("TTS_MAX_INTERVAL", "480"))


def validate():
    missing = [
        name
        for name, val in [
            ("TWITCH_CHANNEL", TWITCH_CHANNEL),
            ("OPENROUTER_API_KEY", OPENROUTER_API_KEY),
        ]
        if not val
    ]
    if not TWITCH_TOKENS:
        missing.append("TWITCH_TOKENS")
    if missing:
        raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")
