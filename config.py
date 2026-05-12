from dotenv import load_dotenv
import os

load_dotenv(".env.development")

class Config:
    # Telegram Bot Token
    TELEGRAM_BOT_TOKEN = os.getenv('BOT_TOKEN')
    # Gemini API Key
    GEMINI_API_KEY = os.getenv('API_KEY')