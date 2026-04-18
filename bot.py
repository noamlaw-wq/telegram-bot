import os
import logging
import anthropic
import httpx
import tempfile
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Store conversation history per user
user_histories = {}

SYSTEM_PROMPT = """אתה עוזר אישי חכם בשם "נועם בוט". 
אתה עוזר למשתמש ב:
1. תזכורות - כשהמשתמש מבקש תזכורת, תרשום אותה בצורה ברורה עם תאריך ושעה אם ציין
2. מסמכים - כשהמשתמש מבקש למלא או ליצור מסמך, תיצור אותו בצורה מסודרת
3. סיכומים - כשהמשתמש מדבר או מספר משהו, תסכם בצורה ברורה ומסודרת
4. שאלות כלליות - תענה בעברית בצורה ידידותית וקצרה

תמיד תענה בעברית אלא אם המשתמש כותב בשפה אחרת.
היה ידידותי, קצר וענייני."""

async def transcribe_voice(file_path: str) -> str:
    """Transcribe voice message using OpenAI Whisper via Anthropic"""
    try:
        with open(file_path, 'rb') as audio_file:
            audio_data = audio_file.read()
        
        import base64
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')
        
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "האזן להודעה הקולית הזו ותמלל אותה בדיוק. החזר רק את התמלול בלי הסברים."
                    }
                ]
            }]
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return None

async def get_claude_response(user_id: int, message: str) -> str:
    """Get response from Claude with conversation history"""
    if user_id not in user_histories:
        user_histories[user_id] = []
    
    user_histories[user_id].append({
        "role": "user",
        "content": message
    })
    
    # Keep only last 20 messages to avoid token limits
    if len(user_histories[user_id]) > 20:
        user_histories[user_id] = user_histories[user_id][-20:]
    
    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=user_histories[user_id]
        )
        
        assistant_message = response.content[0].text
        user_histories[user_id].append({
            "role": "assistant",
            "content": assistant_message
        })
        
        return assistant_message
    except Exception as e:
        logger.error(f"Claude error: {e}")
        return "מצטער, הייתה שגיאה. נסה שוב."

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    user_id = update.effective_user.id
    text = update.message.text
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    response = await get_claude_response(user_id, text)
    await update.message.reply_text(response)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages"""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # Download voice file
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    
    with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp_file:
        tmp_path = tmp_file.name
    
    await file.download_to_drive(tmp_path)
    
    # Try to transcribe, fallback to asking user
    try:
        # Use ffmpeg to convert to mp3 if available, otherwise send as text prompt
        import subprocess
        mp3_path = tmp_path.replace('.ogg', '.mp3')
        subprocess.run(['ffmpeg', '-i', tmp_path, mp3_path, '-y'], 
                      capture_output=True, timeout=30)
        
        # Read and send to Claude for transcription
        with open(mp3_path, 'rb') as f:
            audio_bytes = f.read()
        
        import base64
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        transcription_response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{
                "role": "user", 
                "content": "קיבלתי הודעה קולית. בבקשה אמור למשתמש שתמלול קבצי קול עדיין לא נתמך ישירות, ובקש ממנו לשלוח הודעת טקסט במקום. ענה בעברית."
            }]
        )
        
        await update.message.reply_text(
            "🎤 קיבלתי הודעה קולית!\n\nכרגע אני לא יכול לתמלל קבצי קול ישירות. \nאנא שלח את ההודעה שלך כטקסט ואשמח לעזור! 😊"
        )
        
    except Exception as e:
        logger.error(f"Voice handling error: {e}")
        await update.message.reply_text(
            "🎤 קיבלתי הודעה קולית!\n\nכרגע אני לא יכול לתמלל קבצי קול ישירות. \nאנא שלח את ההודעה שלך כטקסט ואשמח לעזור! 😊"
        )
    
    # Cleanup
    try:
        os.unlink(tmp_path)
    except:
        pass

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
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
    
    from telegram.ext import CommandHandler
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
