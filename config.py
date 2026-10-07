"""Runtime configuration is read from environment variables."""
import os
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ALLOWED_USERS = [int(x) for x in os.getenv("ALLOWED_USERS", "").split(",") if x.strip().isdigit()]
MAX_SIMULATIONS = int(os.getenv("MAX_SIMULATIONS", "20"))
