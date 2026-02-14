import os

BOT_TOKEN = os.getenv("8141286032:AAE69w_l0b-LUmP6qsfHUIVHVqUqbSfyEks", "8141286032:AAE69w_l0b-LUmP6qsfHUIVHVqUqbSfyEks")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@adapter_uronxo")
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/adapter_uronxo")
ADMIN_IDS = [int(x) for x in os.getenv("7923617602", "0").split(",")]
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://yourdomain.com")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))