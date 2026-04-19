import os
import logging
import anthropic
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8604793274:AAH9NI9HwpLH-bYcLu5V5WFYsket2WufTt0")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

user_histories = {}

SYSTEM_PROMPT = """אתה עוזר אישי חכם בשם "נועם בוט". 
אתה עוזר למשתמש ב:
1. תזכורות - כשהמשתמש מבקש תזכורת, תרשום אותה בצורה ברורה עם תאריך ושעה אם ציין
2. מסמכים - כשהמשתמש מבקש למלא או ליצור מסמך, תיצור אותו בצורה מסודרת
3. סיכומים - כשהמשתמש מדבר או מספר משהו, תסכם בצורה ברורה ומסודרת
4. שאלות כלליות - תענה בעברית בצורה ידידותית וקצרה

תמיד תענה בעברית אלא אם המשתמש כותב בשפה אחרת.
היה ידידותי, קצר וענייני."""


async def get_claude_response(user_id: int, message: str) -> str:
    if user_id not in user_histories:
        user_histories[user_id] = []

    user_histories[user_id].append({"role": "user", "content": message})

    if len(user_histories[user_id]) > 20:
        user_histories[user_id] = user_histories[user_id][-20:]

    try:
        response = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=user_histories[user_id],
        )
        assistant_message = response.content[0].text
        user_histories[user_id].append({"role": "assistant", "content": assistant_message})
        return assistant_message
    except Exception as e:
        logger.error(f"Claude error: {e}")
        return "מצטער, הייתה שגיאה. נסה שוב."


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    response = await get_claude_response(user_id, text)
    await update.message.reply_text(response)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎤 קיבלתי הודעה קולית!\n\nכרגע אני לא יכול לתמלל קבצי קול ישירות.\nאנא שלח את ההודעה שלך כטקסט ואשמח לעזור! 😊"
    )


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "שלום! 👋 אני העוזר האישי שלך.\n\n"
        "אני יכול לעזור לך עם:\n"
        "📝 תזכורות\n"
        "📄 מסמכים\n"
        "📋 סיכומים\n"
        "💬 שאלות כלליות\n\n"
        "פשוט כתוב לי מה אתה צריך!"
    )


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
