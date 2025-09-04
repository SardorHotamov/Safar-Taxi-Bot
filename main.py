import os
from telegram.ext import Application
import logging

# Loglashni sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------ ENV ------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 10000))

logger.info(f"BOT_TOKEN: {BOT_TOKEN[:5]}...")  # Faqat boshini ko‘rsatamiz
logger.info(f"WEBHOOK_URL: {WEBHOOK_URL}")
logger.info(f"PORT: {PORT}")

if not BOT_TOKEN or not WEBHOOK_URL:
    logger.error("BOT_TOKEN yoki WEBHOOK_URL noto‘g‘ri belgilangan!")
    raise ValueError("BOT_TOKEN yoki WEBHOOK_URL noto‘g‘ri belgilangan!")

def main():
    logger.info("Ilova ishga tushmoqda")
    app = Application.builder().token(BOT_TOKEN).build()
    logger.info("Application obyekti yaratildi")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=WEBHOOK_URL + "/webhook"
    )

if __name__ == "__main__":
    main()