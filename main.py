import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from config import BOT_TOKEN, ALLOWED_USERS, DEFAULT_COUNT, DEFAULT_THREADS, DEFAULT_DELAY
from sms_bomber import SMSBomber
from call_bomber import CallBomber
from wa_bomber import WABomber
from utils.logger import setup_logger

logger = setup_logger()
state = {}

def ok(uid):
    return uid in ALLOWED_USERS

async def start(u, c):
    if not ok(u.effective_user.id):
        return await u.message.reply_text("Not allowed")
    kb = [
        [InlineKeyboardButton("SMS Bomb", callback_data="m_sms")],
        [InlineKeyboardButton("Call Bomb", callback_data="m_call")],
        [InlineKeyboardButton("WA Bomb", callback_data="m_wa")],
        [InlineKeyboardButton("All In One", callback_data="m_all")],
    ]
    await u.message.reply_text("Mode select karo:", reply_markup=InlineKeyboardMarkup(kb))

async def mode(u, c):
    q = u.callback_query
    await q.answer()
    if not ok(q.from_user.id):
        return
    m = q.data[2:]
    state[q.from_user.id] = {"mode": m}
    await q.edit_message_text(f"Mode: {m}. Ab target number bhejo:")

async def msg(u, c):
    uid = u.effective_user.id
    if not ok(uid):
        return
    t = u.message.text.strip()
    st = state.get(uid)
    if not st:
        return await u.message.reply_text("Pehle /start karo")
    if "phone" not in st:
        st["phone"] = t
        return await u.message.reply_text(f"Count? (default {DEFAULT_COUNT})")
    try:
        n = int(t)
    except Exception:
        n = DEFAULT_COUNT
    p = st["phone"]
    m = st["mode"]
    await u.message.reply_text(f"Start {m} x {n} -> {p}")
    sent = 0
    tasks = []
    if m in ("sms", "all"):
        tasks.append(SMSBomber().bomb(p, n, DEFAULT_THREADS, DEFAULT_DELAY))
    if m in ("call", "all"):
        tasks.append(CallBomber().bomb(p, n, 2.0))
    if m in ("wa", "all"):
        tasks.append(WABomber().bomb(p, n))
    res = await asyncio.gather(*tasks, return_exceptions=True)
    for r in res:
        if isinstance(r, int):
            sent += r
    await u.message.reply_text(f"Done! Sent: {sent}")
    state.pop(uid, None)

async def stop(u, c):
    state.pop(u.effective_user.id, None)
    await u.message.reply_text("Stopped")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CallbackQueryHandler(mode, pattern="^m_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
    logger.info("Deal Bomber Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
