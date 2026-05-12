from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv(".env.development")

# Project root (parent of config.py location)
_ROOT = Path(__file__).resolve().parent


class Config:
    TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
    GEMINI_API_KEY = os.getenv("API_KEY")

    DATA_DIR = Path(os.getenv("DATA_DIR", str(_ROOT / "data")))
    RFPS_DIR = DATA_DIR / "rfps"
    PROPOSALS_DIR = DATA_DIR / "proposals"
    DATABASE_PATH = str(DATA_DIR / "rfp_bot.sqlite3")

    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_FROM = os.getenv("SMTP_FROM")

    @staticmethod
    def ensure_data_dirs() -> None:
        Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        Config.RFPS_DIR.mkdir(parents=True, exist_ok=True)
        Config.PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
