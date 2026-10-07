"""Consent-first Telegram bot. Deliberately performs dry-run simulations only."""
import asyncio
import logging
import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, ConversationHandler, filters)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("safe_console")
NUMBER, COUNT = range(2)
PHONE_RE = re.compile(r"^\+?[1-9]\d{7,14}$")
MAX_COUNT = max(1, min(100, int(os.getenv("MAX_SIMULATIONS", "20"))))


def allowed_ids():
    return {int(x.strip()) for x in os.getenv("ALLOWED_USERS", "").split(",") if x.strip().isdigit()}

def is_authorized(update):
    ids = allowed_ids()
    return bool(ids and update.effective_user and update.effective_user.id in ids)

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Start safe dry-run", callback_data="begin")],
        [InlineKeyboardButton("Stop / cancel", callback_data="stop")],
        [InlineKeyboardButton("Help", callback_data="help")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.effective_message.reply_text("Access denied. Configure ALLOWED_USERS with your Telegram numeric user ID.")
        return
    await update.effective_message.reply_text(
        "Safe Messaging Test Console\n\nThis bot does not send calls, SMS, WhatsApp messages, or OTPs. "
        "The number is only validated and masked; the requested count runs as a local dry-run simulation.",
        reply_markup=menu())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.effective_message.reply_text("Access denied."); return
    await update.effective_message.reply_text("Commands: /start, /help, /status, /stop.\nUse Start safe dry-run, enter a test number and a simulation count (1–%d). Nothing is sent to that number." % MAX_COUNT, reply_markup=menu())

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.effective_message.reply_text("Access denied."); return
    job = context.user_data.get("job")
    await update.effective_message.reply_text("Dry-run running." if job and not job.done() else "No simulation is running.", reply_markup=menu())

async def begin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_authorized(update):
        await q.edit_message_text("Access denied."); return ConversationHandler.END
    await q.edit_message_text("Enter a test phone number in international format (e.g. +14155550123). It will not receive anything.")
    return NUMBER

async def got_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = update.message.text.strip()
    if not PHONE_RE.fullmatch(number):
        await update.message.reply_text("Invalid format. Use international digits, optionally starting with +. Try again or /stop.")
        return NUMBER
    context.user_data["masked_number"] = number[-4:].rjust(min(4, len(number)), "•")
    await update.message.reply_text(f"Validated; stored only as masked …{context.user_data['masked_number']}. Enter dry-run count (1–{MAX_COUNT}).")
    return COUNT

async def simulate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    if not raw.isdigit() or not 1 <= int(raw) <= MAX_COUNT:
        await update.message.reply_text(f"Enter a whole number from 1 to {MAX_COUNT}, or /stop.")
        return COUNT
    count = int(raw)
    await update.message.reply_text(f"Starting {count} local dry-run checks for …{context.user_data['masked_number']}. No network messaging will occur. Press Stop to cancel.", reply_markup=menu())
    async def work():
        for i in range(count):
            await asyncio.sleep(0.25)
            if i == 0 or (i + 1) % 5 == 0 or i + 1 == count:
                try:
                    await update.effective_chat.send_message(f"Dry-run progress: {i+1}/{count}")
                except Exception:
                    log.exception("Could not report progress")
    task = asyncio.create_task(work())
    context.user_data["job"] = task
    try:
        await task
        await update.effective_chat.send_message("Dry-run complete. No message or call was sent.", reply_markup=menu())
    except asyncio.CancelledError:
        await update.effective_chat.send_message("Dry-run stopped.", reply_markup=menu())
    finally:
        context.user_data.pop("job", None)
        context.user_data.pop("masked_number", None)
    return ConversationHandler.END

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.effective_message.reply_text("Access denied."); return ConversationHandler.END
    task = context.user_data.get("job")
    if task and not task.done():
        task.cancel()
    context.user_data.pop("masked_number", None)
    await update.effective_message.reply_text("Stopped / cleared.", reply_markup=menu())
    return ConversationHandler.END

async def callback_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_authorized(update):
        await q.edit_message_text("Access denied."); return ConversationHandler.END
    task = context.user_data.get("job")
    if task and not task.done(): task.cancel()
    context.user_data.pop("masked_number", None)
    await q.edit_message_text("Stopped / cleared.", reply_markup=menu())
    return ConversationHandler.END

async def callback_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_authorized(update): await q.edit_message_text("Access denied."); return
    await q.edit_message_text("Safe dry-run only: no real messages or calls. Commands: /start /help /status /stop", reply_markup=menu())

def main():
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        raise RuntimeError("Set BOT_TOKEN in environment / Heroku Config Vars")
    app = Application.builder().token(token).build()
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(begin, pattern="^begin$")],
        states={NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_number)],
                COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, simulate)]},
        fallbacks=[CommandHandler("stop", stop), CallbackQueryHandler(callback_stop, pattern="^stop$")],
        per_user=True, per_chat=True)
    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status)); app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CallbackQueryHandler(callback_stop, pattern="^stop$"))
    app.add_handler(CallbackQueryHandler(callback_help, pattern="^help$"))
    app.run_polling()

if __name__ == "__main__": main()
