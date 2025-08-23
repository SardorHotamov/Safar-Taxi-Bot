import os
from dotenv import load_dotenv  # load_dotenv import qilish
import telegram

# .env dan token olish
load_dotenv()  # .env faylidan o'zgaruvchilarni yuklash
BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render'dan olingan URL

# Bot obyekti yaratish
bot = telegram.Bot(token=BOT_TOKEN)

# Webhook URL'sini sozlash
webhook_url = f"https://{RENDER_EXTERNAL_URL}/webhook"
bot.set_webhook(url=webhook_url)

print(f"Webhook sozlandi: {webhook_url}")