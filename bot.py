# deploy_this.py - Deploy to cloud
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import aiohttp
import asyncio

TOKEN = os.environ.get('TELEGRAM_TOKEN')
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')

async def query_ai(prompt):
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "nousresearch/nous-hermes-2-mixtral-8x7b-dpo",
            "messages": [{"role": "user", "content": prompt}]
        }
        async with session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers, json=data
        ) as resp:
            result = await resp.json()
            return result['choices'][0]['message']['content']

async def handle_message(update: Update, context):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    response = await query_ai(update.message.text)
    await update.message.reply_text(response)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
