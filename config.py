import os
from dotenv import load_dotenv

# Try to load local .env if present; does nothing if not found
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
DB_CHANNEL_ID = int(os.getenv("DB_CHANNEL_ID", "0"))
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
PORT = int(os.getenv("PORT", "8080"))
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = f"{WEBHOOK_HOST.rstrip('/')}{WEBHOOK_PATH}" if WEBHOOK_HOST else ""

if not BOT_TOKEN or not MONGO_URI or not OWNER_ID:
    raise ValueError(
        "Missing critical configuration. Please set BOT_TOKEN, OWNER_ID, and MONGO_URI (or MONGODB_URI) "
        f"either in your environment variables or in a local .env file. "
        f"Status - BOT_TOKEN: {'Found' if BOT_TOKEN else 'Missing'}, "
        f"OWNER_ID: {'Found' if OWNER_ID else 'Missing'}, "
        f"MONGO_URI/MONGODB_URI: {'Found' if MONGO_URI else 'Missing'}"
    )
