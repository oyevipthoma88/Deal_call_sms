#!/usr/bin/env python3
"""
Deal_call_sms - Premium Bomber Bot
Credits + Keys + Force Join + Progress Bar + Multi-User
Based on CUSTOME_SMS_PREMIUM_SAFE.py (cleaned & fixed)
"""

import asyncio
import logging
import sqlite3
import re
import sys
import random
import string
from datetime import datetime
from typing import Dict, List, Tuple
from uuid import uuid4

import httpx
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters, ContextTypes,
)
from telegram.constants import ParseMode

from config import (
    BOT_TOKEN, ALLOWED_USERS, DEFAULT_COUNT, DEFAULT_THREADS,
    DEFAULT_DELAY,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DB_PATH = "bomber.db"
FORCE_CHANNELS = []  # optional, add channel usernames if needed
OWNER = "@oyevipthoma88"

# ============================================
# DATABASE
# ============================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, credits INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY, target TEXT NOT NULL, message TEXT NOT NULL,
        status TEXT DEFAULT 'pending', total_sms INTEGER DEFAULT 0,
        success_count INTEGER DEFAULT 0, fail_count INTEGER DEFAULT 0,
        credit_used INTEGER DEFAULT 0, user_id INTEGER, chat_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS keys (
        key_string TEXT PRIMARY KEY, credits INTEGER NOT NULL,
        max_uses INTEGER NOT NULL, used_count INTEGER DEFAULT 0,
        created_by INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS redemptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, key_string TEXT, user_id INTEGER,
        redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()
    conn.close()

init_db()

def get_user_credits(uid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    if not r:
        c.execute("INSERT INTO users (user_id, credits) VALUES (?, 0)", (uid,))
        conn.commit()
        conn.close()
        return 0
    conn.close()
    return r[0]

def update_credits(uid, delta):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (delta, uid))
    conn.commit()
    conn.close()

def deduct_credits(uid, amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    if not r:
        c.execute("INSERT INTO users (user_id, credits) VALUES (?, 0)", (uid,))
        conn.commit()
        conn.close()
        return False
    if r[0] >= amount:
        c.execute("UPDATE users SET credits = credits - ? WHERE user_id=?", (amount, uid))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def gen_key(n=12):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

def add_key(k, credits, max_uses, by):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO keys VALUES (?,?,?,0,?)", (k, credits, max_uses, by))
    conn.commit()
    conn.close()

def redeem_key(k, uid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT credits, max_uses, used_count FROM keys WHERE key_string=?", (k,))
    r = c.fetchone()
    if not r:
        conn.close()
        return False
    credits, max_uses, used = r
    if used >= max_uses:
        conn.close()
        return False
    c.execute("SELECT 1 FROM redemptions WHERE key_string=? AND user_id=?", (k, uid))
    if c.fetchone():
        conn.close()
        return False
    c.execute("UPDATE keys SET used_count = used_count + 1 WHERE key_string=?", (k,))
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (credits, uid))
    if c.rowcount == 0:
        c.execute("INSERT INTO users (user_id, credits) VALUES (?,?)", (uid, credits))
    c.execute("INSERT INTO redemptions (key_string, user_id) VALUES (?,?)", (k, uid))
    conn.commit()
    conn.close()
    return True

# ============================================
# KEYBOARD
# ============================================
BTN_BOMB = "💣 Launch Bomb"
BTN_BAL = "💰 Balance"
BTN_HIST = "📜 History"
BTN_STATUS = "📊 Status"
BTN_REDEEM = "🔑 Redeem Key"
BTN_ONLINE = "📡 Online Devices"
BTN_MANAGE = "⚙️ Manage FB"
BTN_GENKEY = "🔑 Gen Key"

USER_BTNS = [BTN_BOMB, BTN_BAL, BTN_HIST, BTN_STATUS, BTN_REDEEM]
ADMIN_BTNS = [BTN_ONLINE, BTN_MANAGE, BTN_GENKEY]
ALL_BTNS = USER_BTNS + ADMIN_BTNS

def is_admin(uid):
    return uid in ALLOWED_USERS

def kb_main(uid):
    rows = [
        [KeyboardButton(BTN_BOMB), KeyboardButton(BTN_BAL)],
        [KeyboardButton(BTN_HIST), KeyboardButton(BTN_STATUS)],
        [KeyboardButton(BTN_REDEEM)],
    ]
    if is_admin(uid):
        rows.append([KeyboardButton(BTN_ONLINE), KeyboardButton(BTN_MANAGE)])
        rows.append([KeyboardButton(BTN_GENKEY)])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)

# ============================================
# HANDLERS
# ============================================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    credits = get_user_credits(uid)
    role = "👑 ADMIN" if is_admin(uid) else "⭐ USER"
    txt = (
        "🔥 *PREMIUM XIPHER BOMBER*\n\n"
        f"👤 User ID: `{uid}`\n"
        f"💰 Credits: {credits}\n"
        f"🎭 Role: {role}\n"
        f"⚙️ Owner: {OWNER}\n\n"
        "Use keyboard below ✨"
    )
    await update.message.reply_text(txt, reply_markup=kb_main(uid), parse_mode=ParseMode.MARKDOWN)

async def balance_cmd(update, ctx):
    uid = update.effective_user.id
    credits = get_user_credits(uid)
    await update.message.reply_text(f"💰 Balance: *{credits}* credits", parse_mode=ParseMode.MARKDOWN)

async def history_cmd(update, ctx):
    uid = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 10", (uid,))
    jobs = [dict(r) for r in c.fetchall()]
    conn.close()
    if not jobs:
        await update.message.reply_text("No jobs yet.")
        return
    txt = "📜 *Recent Jobs*\n\n"
    for j in jobs:
        emoji = {"pending": "⏳", "running": "🔄", "completed": "✅", "failed": "❌"}.get(j["status"], "❓")
        txt += f"{emoji} `{j['id']}` → `{j['target']}` ({j['status']})\n"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def status_cmd(update, ctx):
    await history_cmd(update, ctx)

async def redeem_cmd(update, ctx):
    uid = update.effective_user.id
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /redeem <key>")
        return
    if redeem_key(args[0].strip(), uid):
        credits = get_user_credits(uid)
        await update.message.reply_text(f"✅ Redeemed! Balance: *{credits}*", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ Invalid or expired key.")

async def addkey_cmd(update, ctx):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /addkey <credits> <max_uses>")
        return
    try:
        credits, max_uses = int(args[0]), int(args[1])
    except:
        await update.message.reply_text("❌ Invalid values.")
        return
    k = gen_key()
    add_key(k, credits, max_uses, uid)
    await update.message.reply_text(f"✅ Key: `{k}`\nCredits: {credits} | Max: {max_uses}", parse_mode=ParseMode.MARKDOWN)

async def addcredits_cmd(update, ctx):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /addcredits <user_id> <amount>")
        return
    try:
        target, amount = int(args[0]), int(args[1])
    except:
        await update.message.reply_text("❌ Invalid.")
        return
    update_credits(target, amount)
    await update.message.reply_text(f"✅ Added {amount} to {target}.")

async def broadcast_cmd(update, ctx):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    msg = update.message.text.replace("/broadcast", "").strip()
    if not msg:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    uids = [r[0] for r in c.fetchall()]
    conn.close()
    sent, fail = 0, 0
    for u in uids:
        try:
            await ctx.bot.send_message(u, msg)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            fail += 1
    await update.message.reply_text(f"📢 Sent: {sent} | Failed: {fail}")

# ============================================
# BOMB WIZARD
# ============================================
(TARGET, MESSAGE, COUNT, SPEED) = range(4)

async def bomb_start(update, ctx):
    await update.message.reply_text(
        "📞 Enter target (with country code, e.g. 919876543210):\n/cancel to abort"
    )
    return TARGET

async def bomb_target(update, ctx):
    t = update.message.text.strip()
    if t in ALL_BTNS:
        ctx.user_data.clear()
        await button_router(update, ctx)
        return ConversationHandler.END
    if not t.isdigit() or len(t) < 10:
        await update.message.reply_text("❌ Valid numeric phone number daalo.")
        return TARGET
    ctx.user_data["target"] = t
    await update.message.reply_text("✏️ Message likho:")
    return MESSAGE

async def bomb_message(update, ctx):
    t = update.message.text
    if t in ALL_BTNS:
        ctx.user_data.clear()
        await button_router(update, ctx)
        return ConversationHandler.END
    ctx.user_data["message"] = t
    credits = get_user_credits(update.effective_user.id)
    await update.message.reply_text(
        f"📨 Kitne SMS? (Balance: *{credits}*, 1 SMS = 1 credit)",
        parse_mode=ParseMode.MARKDOWN
    )
    return COUNT

async def bomb_count(update, ctx):
    t = update.message.text
    if t in ALL_BTNS:
        ctx.user_data.clear()
        await button_router(update, ctx)
        return ConversationHandler.END
    try:
        n = int(t)
        if n <= 0: raise ValueError
    except:
        await update.message.reply_text("❌ Positive integer daalo.")
        return COUNT
    credits = get_user_credits(update.effective_user.id)
    if n > credits:
        await update.message.reply_text(f"⚠️ Sirf {credits} credits hain.")
        return COUNT
    ctx.user_data["count"] = n
    kb = [
        [InlineKeyboardButton("🐢 Slow (1s)", callback_data="sp_slow")],
        [InlineKeyboardButton("🐇 Medium (0.5s)", callback_data="sp_med")],
        [InlineKeyboardButton("🚀 Fast (0.1s)", callback_data="sp_fast")],
    ]
    await update.message.reply_text("⚡ Speed select karo:", reply_markup=InlineKeyboardMarkup(kb))
    return SPEED

async def bomb_speed(update, ctx):
    q = update.callback_query
    await q.answer()
    delay_map = {"sp_slow": 1.0, "sp_med": 0.5, "sp_fast": 0.1}
    delay = delay_map.get(q.data, 0.5)
    uid = q.from_user.id
    target = ctx.user_data["target"]
    message = ctx.user_data["message"]
    count = ctx.user_data["count"]
    if get_user_credits(uid) < count:
        await q.message.reply_text("❌ Insufficient credits.")
        return ConversationHandler.END
    if not deduct_credits(uid, count):
        await q.message.reply_text("❌ Credit deduct failed.")
        return ConversationHandler.END
    job_id = str(uuid4())[:8]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO jobs (id, target, message, status, total_sms, user_id, chat_id) VALUES (?,?,?,?,?,?,?)",
              (job_id, target, message, "running", count, uid, q.message.chat_id))
    conn.commit()
    conn.close()
    await q.message.reply_text(
        f"✅ Job launched!\n🆔 `{job_id}`\n📞 `{target}`\n📨 {count} SMS\n⏱️ {delay}s delay",
        parse_mode=ParseMode.MARKDOWN
    )
    # Async bomb task
    asyncio.create_task(_run_bomb(job_id, target, count, delay, uid, q.message.chat_id))
    ctx.user_data.clear()
    return ConversationHandler.END

async def _run_bomb(job_id, target, count, delay, uid, chat_id):
    """Placeholder bomber - add real APIs via data/sms_apis.json."""
    import json, os
    apis = []
    if os.path.exists("data/sms_apis.json"):
        with open("data/sms_apis.json") as f:
            apis = json.load(f)
    success, fail = 0, 0
    msg_id = None
    for i in range(count):
        ok = False
        if apis:
            api = random.choice(apis)
            try:
                url = api["url"]
                headers = api.get("headers", {})
                body = {k: str(v).replace("{phone}", target) for k, v in api.get("body", {}).items()}
                async with httpx.AsyncClient(timeout=10) as cli:
                    r = await cli.post(url, headers=headers, json=body) if api.get("method") == "POST" else await cli.get(url, headers=headers)
                    ok = 200 <= r.status_code < 300
            except:
                ok = False
        else:
            ok = True  # dry run if no APIs
        if ok: success += 1
        else: fail += 1
        # Progress
        pct = int((i + 1) / count * 100)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        text = (
            f"💣 *Job* `{job_id}`\n"
            f"📞 `{target}`\n"
            f"{bar} {pct}%\n"
            f"✅ {success} | ❌ {fail}"
        )
        try:
            if msg_id:
                await BOT.edit_message_text(text, chat_id=chat_id, message_id=msg_id, parse_mode=ParseMode.MARKDOWN)
            else:
                m = await BOT.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN)
                msg_id = m.message_id
        except:
            pass
        await asyncio.sleep(delay)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE jobs SET status='completed', success_count=?, fail_count=?, credit_used=? WHERE id=?",
              (success, fail, success, job_id))
    conn.commit()
    conn.close()
    if fail > 0:
        update_credits(uid, fail)

async def cancel_conv(update, ctx):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

# ============================================
# BUTTON ROUTER
# ============================================
async def button_router(update, ctx):
    text = update.message.text
    uid = update.effective_user.id

    if text == BTN_BOMB:
        return await bomb_start(update, ctx)
    elif text == BTN_BAL:
        await balance_cmd(update, ctx)
    elif text == BTN_HIST:
        await history_cmd(update, ctx)
    elif text == BTN_STATUS:
        await status_cmd(update, ctx)
    elif text == BTN_REDEEM:
        ctx.user_data["awaiting_redeem"] = True
        await update.message.reply_text("🔑 Key bhejo:")
    elif text == BTN_ONLINE and is_admin(uid):
        await update.message.reply_text("📡 Online devices feature: add Firebase integration.")
    elif text == BTN_MANAGE and is_admin(uid):
        await update.message.reply_text("⚙️ Manage Firebase: /addfb <url>")
    elif text == BTN_GENKEY and is_admin(uid):
        await update.message.reply_text("🔑 Use: /addkey <credits> <max_uses>")
    elif ctx.user_data.get("awaiting_redeem"):
        k = text.strip()
        if redeem_key(k, uid):
            credits = get_user_credits(uid)
            await update.message.reply_text(f"✅ Redeemed! Balance: *{credits}*", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("❌ Invalid key.")
        ctx.user_data.pop("awaiting_redeem", None)

# ============================================
# MAIN
# ============================================
BOT = None

def main():
    global BOT
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN missing. Create .env file.")
        sys.exit(1)
    app = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()
    BOT = app.bot

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("bomb", bomb_start),
            MessageHandler(filters.Regex(f"^{re.escape(BTN_BOMB)}$"), bomb_start),
        ],
        states={
            TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, bomb_target)],
            MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bomb_message)],
            COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bomb_count)],
            SPEED: [CallbackQueryHandler(bomb_speed, pattern="^sp_(slow|med|fast)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("redeem", redeem_cmd))
    app.add_handler(CommandHandler("addkey", addkey_cmd))
    app.add_handler(CommandHandler("addcredits", addcredits_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_router))

    logger.info("Premium Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
