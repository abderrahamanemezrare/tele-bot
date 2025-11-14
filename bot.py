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
import os

# -----------------------------------------
# Setup
# -----------------------------------------

BOT_TOKEN = os.getenv("BOT_TOKEN")   # ← IMPORTANT FOR RENDER

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
# /start
# -----------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! Send me vocabulary like this:\n\n"
        "`word: exhilarate\n"
        "definition: to make someone feel very happy`\n",
        parse_mode="Markdown"
    )


# -----------------------------------------
# Save vocabs
# -----------------------------------------

async def save_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if "word:" not in text or "definition:" not in text:
        await update.message.reply_text("Format:\nword: ...\ndefinition: ...")
        return

    lines = text.split("\n")
    word = lines[0].replace("word:", "").strip()
    definition = lines[1].replace("definition:", "").strip()

    db.insert({
        "user_id": update.message.chat_id,
        "word": word,
        "definition": definition
    })

    await update.message.reply_text(f"Saved! I'll remind you about *{word}*.", parse_mode="Markdown")

    await schedule_reminders(context.application, update.message.chat_id, word, definition)


# -----------------------------------------
# Reminder button handler
# -----------------------------------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, word = query.data.split("|")

    if action == "remember":
        await query.edit_message_text(f"Nice! You remembered *{word}* 🎉", parse_mode="Markdown")

    else:
        await query.edit_message_text("No worries, I’ll remind you again 💪")

        entry = db.get((Word.word == word) & (Word.user_id == query.from_user.id))
        if entry:
            await schedule_reminders(context.application, query.from_user.id, word, entry["definition"])


# -----------------------------------------
# /list command
# -----------------------------------------

async def list_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    entries = db.search(Word.user_id == user_id)

    if not entries:
        await update.message.reply_text("You don’t have any saved words yet.")
        return

    msg = "📚 *Your saved words:*\n\n"
    for e in entries:
        msg += f"• *{e['word']}* — {e['definition']}\n"

    await update.message.reply_text(msg, parse_mode="Markdown")


# -----------------------------------------
# Main
# -----------------------------------------

def main():
    scheduler.start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_words))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_word))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()


if __name__ == "__main__":
    main()
