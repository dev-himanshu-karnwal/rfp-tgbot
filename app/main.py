from __future__ import annotations

from telegram.ext import ApplicationBuilder

from app.controllers.rfp_handlers import register_handlers
from app.storage.db import init_db
from config import Config


def build_application():
    if not Config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured")
    init_db()
    application = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()
    register_handlers(application)
    return application


def run() -> None:
    build_application().run_polling()


if __name__ == "__main__":
    run()
