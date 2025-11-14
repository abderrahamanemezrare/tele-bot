import logging
from datetime import datetime, timedelta
from tinydb import TinyDB, Query
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# -----------------------------------------
# Setup
# -----------------------------------------

BOT_TOKEN = "8201765784:AAGBY0bAs6SXrYI4_LjN7SYYYwqDPbPE4no"
db = TinyDB("database.json")
Word = Query()

logging.basicConfig(level=logging.INFO)

scheduler = AsyncIOScheduler()


# -----------------------------------------
# Helper: schedule reminders
# -----------------------------------------

async def schedule_reminders(app, user_id, word, definition):
    intervals = [
        ("24h", 24),
        ("3d", 72),
        ("7d", 168)
    ]

    for tag, hours in intervals:
        run_time = datetime.utcnow() + timedelta(hours=hours)

        scheduler.add_job(
            send_reminder,
            "date",
            run_date=run_time,
            args=[app, user_id, word, definition]
        )


async def send_reminder(app, user_id, word, definition):
    """Send blurred definition."""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ I remember", callback_data=f"remember|{word}"),
            InlineKeyboardButton("❌ I forgot", callback_data=f"forgot|{word}")
        ]
    ])

    text = (
        f"🔔 *Review your word!* \n\n"
        f"📘 *Word:* {word}\n"
        f"📖 *Definition:* ||{definition}||"
    )

    await app.bot.send_message(
        chat_id=user_id,
        text=text,
        parse_mode="MarkdownV2",
        reply_markup=keyboard
    )


# -----------------------------------------
# /start command
# -----------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! Send me English vocabulary like this:\n\n"
        "`word: exhilarate\n"
        "definition: to make someone feel very happy`\n\n"
        "I will remind you in 24h, 3 days, and 1 week!",
        parse_mode="Markdown"
    )


# -----------------------------------------
# Save vocabulary
# -----------------------------------------

async def save_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if "word:" not in text or "definition:" not in text:
        await update.message.reply_text("Please send in format:\nword: ...\ndefinition: ...")
        return

    lines = text.split("\n")
    word = lines[0].replace("word:", "").strip()
    definition = lines[1].replace("definition:", "").strip()

    # Store the word
    db.insert({
        "user_id": update.message.chat_id,
        "word": word,
        "definition": definition
    })

    await update.message.reply_text(f"Saved! I’ll remind you about *{word}* soon.", parse_mode="Markdown")

    # Schedule reminders
    await schedule_reminders(context.application, update.message.chat_id, word, definition)


# -----------------------------------------
# Button handler
# -----------------------------------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, word = query.data.split("|")

    if action == "remember":
        await query.edit_message_text(f"Great! You remembered *{word}* 🎉", parse_mode="Markdown")
    else:
        await query.edit_message_text(f"Don't worry — I'll remind you again later 💪")

        # Fetch definition again
        entry = db.get((Word.word == word) & (Word.user_id == query.from_user.id))
        if entry:
            await schedule_reminders(context.application, query.from_user.id, word, entry["definition"])


# -----------------------------------------
# Main
# -----------------------------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_words))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_word))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Start scheduler INSIDE the event loop
    async def on_startup():
        scheduler.start()

    app.post_init(on_startup)

    app.run_polling()


if __name__ == "__main__":
    main()

