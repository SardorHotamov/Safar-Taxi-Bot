import os
from telegram.ext import Application

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = Application.builder().token(BOT_TOKEN).build()

async def set_webhook():
    await app.bot.set_webhook(url=WEBHOOK_URL)
    print("Webhook sozlandi:", WEBHOOK_URL)

def run_webhook():
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 8443)),
        url_path="webhook",
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(set_webhook())
    run_webhook()