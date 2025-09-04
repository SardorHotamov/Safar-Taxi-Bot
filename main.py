import os
import logging

# Loglashni sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Kod ishga tushdi")
logger.info(f"BOT_TOKEN: {os.getenv('BOT_TOKEN', 'None')[:5]}...")
logger.info(f"WEBHOOK_URL: {os.getenv('WEBHOOK_URL', 'None')}")

if __name__ == "__main__":
    logger.info("Main blok ishga tushdi")