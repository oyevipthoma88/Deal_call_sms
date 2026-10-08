"""
Deal_call_sms - Configuration
Saare secrets .env se read hote hain. Yahan kuch bhi hardcode mat karo.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================
# TELEGRAM
# ============================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError(
        "BOT_TOKEN not set!\n"
        "Create .env file: cp .env.example .env && nano .env"
    )

ALLOWED_USERS = [
    int(x.strip())
    for x in os.getenv("ALLOWED_USERS", "").split(",")
    if x.strip().isdigit()
]

# ============================================
# BOMBING DEFAULTS
# ============================================
DEFAULT_COUNT = int(os.getenv("DEFAULT_COUNT", "50"))
DEFAULT_THREADS = int(os.getenv("DEFAULT_THREADS", "10"))
DEFAULT_DELAY = float(os.getenv("DEFAULT_DELAY", "0.3"))
COUNTRY_CODE = os.getenv("COUNTRY_CODE", "+91")
PROXY = os.getenv("PROXY") or None

# ============================================
# WHATSAPP
# ============================================
WA_MESSAGE = os.getenv("WA_MESSAGE", "OTP Verification Code: 123456")
WA_COUNT = int(os.getenv("WA_COUNT", "10"))

# ============================================
# LOGGING
# ============================================
LOG_FILE = os.getenv("LOG_FILE", "logs/bot.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ============================================
# HTTP
# ============================================
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "20"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))
USER_AGENT_ROTATE = os.getenv("USER_AGENT_ROTATE", "true").lower() == "true"
