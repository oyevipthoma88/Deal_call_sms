# config.py
import os

# Telegram Bot Token (BotFather se le)
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Admin Telegram IDs (jo log bot use kar sakte hain)
ALLOWED_USERS = [123456789]  # Apni Telegram ID daal

# Default bombing settings
DEFAULT_COUNT = 50          # Kitne messages bhejne hain
DEFAULT_THREADS = 10        # Concurrent threads
DEFAULT_DELAY = 0.5         # Delay between requests (seconds)

# Proxy (optional)
PROXY = None  # "http://user:pass@ip:port"

# WhatsApp settings
WA_MESSAGE = "🔥 OTP Verification Code: 123456"
WA_COUNT = 10               # WhatsApp messages count
