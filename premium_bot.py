#!/usr/bin/env python3
import asyncio, logging, sqlite3, random, string, sys, re, json, os
from datetime import datetime
from uuid import uuid4
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from config import BOT_TOKEN, ALLOWED_USERS

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "bomber.db"
OWNER = "@oyevipthoma88"
ADMIN_IDS = list(set(list(ALLOWED_USERS) + [8098146730]))
UNLIMITED = 999_999_999
MAX_PER_JOB = 1000

PLANS = {
    "basic": "🥉 Basic - 500 credits - Rs 99",
    "pro":   "🥈 Pro - 5000 credits - Rs 499",
    "elite": "🥇 Elite - 50000 credits - Rs 2499",
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, credits INTEGER DEFAULT 0, total_gifted INTEGER DEFAULT 0, total_used INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, target TEXT NOT NULL, message TEXT NOT NULL, status TEXT DEFAULT 'pending', total_sms INTEGER DEFAULT 0, success_count INTEGER DEFAULT 0, fail_count INTEGER DEFAULT 0, credit_used INTEGER DEFAULT 0, user_id INTEGER, chat_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS keys (key_string TEXT PRIMARY KEY, credits INTEGER NOT NULL, max_uses INTEGER NOT NULL, used_count INTEGER DEFAULT 0, created_by INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS coupons (code TEXT PRIMARY KEY, credits INTEGER NOT NULL, max_uses INTEGER NOT NULL, used_count INTEGER DEFAULT 0, created_by INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS redemptions (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, user_id INTEGER, kind TEXT, redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()
    conn.close()

init_db()

def is_owner(uid): return uid in ADMIN_IDS

def get_user_credits(uid):
    if is_owner(uid): return UNLIMITED
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    if not r:
        c.execute("INSERT INTO users (user_id, credits) VALUES (?, 0)", (uid,))
        conn.commit(); conn.close(); return 0
    conn.close(); return r[0]

def update_credits(uid, delta):
    if is_owner(uid): return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    if not c.fetchone(): c.execute("INSERT INTO users (user_id, credits) VALUES (?, 0)", (uid,))
    c.execute("UPDATE users SET credits = MAX(0, credits + ?) WHERE user_id=?", (delta, uid))
    conn.commit(); conn.close()

def deduct_credits(uid, amount):
    if is_owner(uid): return True
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    if not r:
        c.execute("INSERT INTO users (user_id, credits) VALUES (?, 0)", (uid,))
        conn.commit(); conn.close(); return False
    if r[0] >= amount:
        c.execute("UPDATE users SET credits = credits - ?, total_used = total_used + ? WHERE user_id=?", (amount, amount, uid))
        conn.commit(); conn.close(); return True
    conn.close(); return False

def gen_code(n=12): return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

def add_key(k, credits, max_uses, by):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO keys (key_string, credits, max_uses, created_by) VALUES (?,?,?,?)", (k, credits, max_uses, by))
    conn.commit(); conn.close()

def add_coupon(code, credits, max_uses, by):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO coupons (code, credits, max_uses, created_by) VALUES (?,?,?,?)", (code, credits, max_uses, by))
    conn.commit(); conn.close()

def redeem_code(code, uid, kind):
    table = "keys" if kind == "key" else "coupons"
    col = "key_string" if kind == "key" else "code"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT credits, max_uses, used_count FROM " + table + " WHERE " + col + "=?", (code,))
    r = c.fetchone()
    if not r: conn.close(); return None
    credits, max_uses, used = r
    if used >= max_uses: conn.close(); return None
    c.execute("SELECT 1 FROM redemptions WHERE code=? AND user_id=? AND kind=?", (code, uid, kind))
    if c.fetchone(): conn.close(); return None
    c.execute("UPDATE " + table + " SET used_count = used_count + 1 WHERE " + col + "=?", (code,))
    c.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, credits) VALUES (?, ?)", (uid, credits))
    else:
        c.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (credits, uid))
    c.execute("INSERT INTO redemptions (code, user_id, kind) VALUES (?,?,?)", (code, uid, kind))
    conn.commit(); conn.close()
    return credits

BTN_BOMB = "💣 Launch Bomb"
BTN_BAL = "💰 Balance"
BTN_HIST = "📜 History"
BTN_STATUS = "📊 Status"
BTN_REDEEM = "🔑 Redeem Key"
BTN_COUPON = "🎟️ Redeem Coupon"
BTN_PREMIUM = "👑 Buy Premium"
BTN_GIFT = "🎁 Gift Credits"
BTN_GENKEY = "🔑 Gen Key"
BTN_GENCOUPON = "🎟️ Gen Coupon"
BTN_STATS = "📊 Stats"

USER_BTNS = [BTN_BOMB, BTN_BAL, BTN_HIST, BTN_STATUS, BTN_REDEEM, BTN_COUPON, BTN_PREMIUM]
ADMIN_BTNS = [BTN_GIFT, BTN_GENKEY, BTN_GENCOUPON, BTN_STATS]
ALL_BTNS = USER_BTNS + ADMIN_BTNS

def kb_main(uid):
    rows = [
        [KeyboardButton(BTN_BOMB), KeyboardButton(BTN_BAL)],
        [KeyboardButton(BTN_HIST), KeyboardButton(BTN_STATUS)],
        [KeyboardButton(BTN_REDEEM), KeyboardButton(BTN_COUPON)],
        [KeyboardButton(BTN_PREMIUM)],
    ]
    if is_owner(uid):
        rows.append([KeyboardButton(BTN_GIFT), KeyboardButton(BTN_GENKEY)])
        rows.append([KeyboardButton(BTN_GENCOUPON), KeyboardButton(BTN_STATS)])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)

async def start(update, ctx):
    uid = update.effective_user.id
    credits = get_user_credits(uid)
    role = "👑 OWNER" if is_owner(uid) else "⭐ USER"
    cred_display = "♾️ UNLIMITED" if is_owner(uid) else str(credits)
    txt = "🔥 *PREMIUM XIPHER BOMBER*\n\n👤 User ID: `" + str(uid) + "`\n💰 Credits: " + cred_display + "\n🎭 Role: " + role + "\n⚙️ Owner: " + OWNER + "\n\nUse keyboard below ✨"
    await update.message.reply_text(txt, reply_markup=kb_main(uid), parse_mode=ParseMode.MARKDOWN)

async def balance_cmd(update, ctx):
    uid = update.effective_user.id
    if is_owner(uid):
        await update.message.reply_text("💰 Balance: *♾️ UNLIMITED* (Owner)", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("💰 Balance: *" + str(get_user_credits(uid)) + "* credits", parse_mode=ParseMode.MARKDOWN)

async def history_cmd(update, ctx):
    uid = update.effective_user.id
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 10", (uid,))
    jobs = [dict(r) for r in c.fetchall()]; conn.close()
    if not jobs:
        await update.message.reply_text("No jobs yet."); return
    txt = "📜 *Recent Jobs*\n\n"
    for j in jobs:
        emoji = {"pending": "⏳", "running": "🔄", "completed": "✅", "failed": "❌"}.get(j["status"], "❓")
        txt += emoji + " `" + j["id"] + "` -> `" + j["target"] + "` (" + j["status"] + ")\n"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def status_cmd(update, ctx): await history_cmd(update, ctx)

async def premium_menu(update, ctx):
    txt = "👑 *PREMIUM PLANS*\n\n"
    for k, v in PLANS.items(): txt += v + "\n"
    txt += "\n💳 *How to Buy:*\n1. Contact owner: " + OWNER + "\n2. Payment ke baad credits add ho jayenge\n\n🎁 *Free Trial:* /freetrial (ek baar)"
    kb = [[InlineKeyboardButton("💳 Contact Owner", url="https://t.me/" + OWNER.replace("@", ""))], [InlineKeyboardButton("🎁 Free Trial", callback_data="claim_free")]]
    await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def freetrial_cmd(update, ctx):
    uid = update.effective_user.id
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT 1 FROM redemptions WHERE code='FREE_TRIAL' AND user_id=?", (uid,))
    if c.fetchone(): conn.close(); await update.message.reply_text("❌ Free trial already claimed!"); return
    c.execute("INSERT INTO redemptions (code, user_id, kind) VALUES ('FREE_TRIAL', ?, 'trial')", (uid,))
    c.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    if not c.fetchone(): c.execute("INSERT INTO users (user_id, credits) VALUES (?, 50)", (uid,))
    else: c.execute("UPDATE users SET credits = credits + 50 WHERE user_id=?", (uid,))
    conn.commit(); conn.close()
    await update.message.reply_text("🎁 *FREE TRIAL ACTIVATED*\n+50 credits added!\nUse /bomb.", parse_mode=ParseMode.MARKDOWN)

async def claim_free_cb(update, ctx):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT 1 FROM redemptions WHERE code='FREE_TRIAL' AND user_id=?", (uid,))
    if c.fetchone(): conn.close(); await q.message.reply_text("❌ Already claimed!"); return
    c.execute("INSERT INTO redemptions (code, user_id, kind) VALUES ('FREE_TRIAL', ?, 'trial')", (uid,))
    c.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    if not c.fetchone(): c.execute("INSERT INTO users (user_id, credits) VALUES (?, 50)", (uid,))
    else: c.execute("UPDATE users SET credits = credits + 50 WHERE user_id=?", (uid,))
    conn.commit(); conn.close()
    await q.message.reply_text("🎁 Free trial activated! +50 credits.")

async def gift_cmd(update, ctx):
    uid = update.effective_user.id
    if not is_owner(uid): await update.message.reply_text("⛔ Owner only."); return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("🎁 *GIFT CREDITS*\n\nUsage: `/gift <user_id> <credits>`\nExample: `/gift 123456789 1000`", parse_mode=ParseMode.MARKDOWN); return
    try:
        target = int(args[0]); amount = int(args[1])
        if amount <= 0 or amount > 1000000: raise ValueError
    except: await update.message.reply_text("❌ Invalid numbers (1-1000000)."); return
    update_credits(target, amount)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE users SET total_gifted = total_gifted + ? WHERE user_id=?", (amount, target))
    if c.rowcount == 0: c.execute("INSERT INTO users (user_id, credits, total_gifted) VALUES (?, ?, ?)", (target, amount, amount))
    conn.commit(); conn.close()
    await update.message.reply_text("🎁 *GIFT SENT*\nTo: `" + str(target) + "`\nCredits: +" + str(amount), parse_mode=ParseMode.MARKDOWN)
    try:
        await ctx.bot.send_message(target, "🎁 *You received a gift!*\n+" + str(amount) + " credits!\nUse /balance.", parse_mode=ParseMode.MARKDOWN)
    except: pass

async def gencoupon_cmd(update, ctx):
    uid = update.effective_user.id
    if not is_owner(uid): await update.message.reply_text("⛔ Owner only."); return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Usage: `/gencoupon <credits> <max_uses> [CODE]`\nExample: `/gencoupon 500 10 WELCOME500`", parse_mode=ParseMode.MARKDOWN); return
    try: credits = int(args[0]); max_uses = int(args[1])
    except: await update.message.reply_text("❌ Invalid numbers."); return
    code = args[2].upper() if len(args) >= 3 else gen_code(10)
    add_coupon(code, credits, max_uses, uid)
    await update.message.reply_text("🎟️ *COUPON CREATED*\n\nCode: `" + code + "`\nCredits: " + str(credits) + "\nMax Uses: " + str(max_uses), parse_mode=ParseMode.MARKDOWN)

async def addkey_cmd(update, ctx):
    uid = update.effective_user.id
    if not is_owner(uid): await update.message.reply_text("⛔ Owner only."); return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Usage: `/addkey <credits> <max_uses>`", parse_mode=ParseMode.MARKDOWN); return
    try: credits = int(args[0]); max_uses = int(args[1])
    except: await update.message.reply_text("❌ Invalid."); return
    k = gen_code()
    add_key(k, credits, max_uses, uid)
    await update.message.reply_text("🔑 Key: `" + k + "`\nCredits: " + str(credits) + " | Max: " + str(max_uses), parse_mode=ParseMode.MARKDOWN)

async def addcredits_cmd(update, ctx):
    uid = update.effective_user.id
    if not is_owner(uid): await update.message.reply_text("⛔ Owner only."); return
    args = ctx.args
    if len(args) < 2: await update.message.reply_text("Usage: `/addcredits <user_id> <amount>`", parse_mode=ParseMode.MARKDOWN); return
    try: target = int(args[0]); amount = int(args[1])
    except: await update.message.reply_text("❌ Invalid."); return
    update_credits(target, amount)
    await update.message.reply_text("✅ Added " + str(amount) + " credits to `" + str(target) + "`", parse_mode=ParseMode.MARKDOWN)

async def stats_cmd(update, ctx):
    uid = update.effective_user.id
    if not is_owner(uid): await update.message.reply_text("⛔ Owner only."); return
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users"); tu = c.fetchone()[0]
    c.execute("SELECT SUM(credits) FROM users"); tc = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM jobs"); tj = c.fetchone()[0]
    c.execute("SELECT SUM(success_count) FROM jobs"); ts = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM coupons"); cp = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM keys"); kk = c.fetchone()[0]
    conn.close()
    await update.message.reply_text("📊 *BOT STATS*\n\n👥 Users: " + str(tu) + "\n💰 Credits: " + str(tc) + "\n💣 Jobs: " + str(tj) + "\n📨 SMS: " + str(ts) + "\n🎟️ Coupons: " + str(cp) + "\n🔑 Keys: " + str(kk), parse_mode=ParseMode.MARKDOWN)

async def broadcast_cmd(update, ctx):
    uid = update.effective_user.id
    if not is_owner(uid): await update.message.reply_text("⛔ Owner only."); return
    msg = update.message.text.replace("/broadcast", "").strip()
    if not msg: await update.message.reply_text("Usage: `/broadcast <msg>`", parse_mode=ParseMode.MARKDOWN); return
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT user_id FROM users"); uids = [r[0] for r in c.fetchall()]; conn.close()
    sent, fail = 0, 0
    for u in uids:
        try: await ctx.bot.send_message(u, msg); sent += 1; await asyncio.sleep(0.05)
        except: fail += 1
    await update.message.reply_text("📢 Sent: " + str(sent) + " | Failed: " + str(fail))

async def gift_cmd(update, ctx):
    uid = update.effective_user.id
    if not is_owner(uid): await update.message.reply_text("⛔ Owner only."); return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("🎁 *GIFT CREDITS*\n\nUsage: `/gift <user_id> <credits>`\nExample: `/gift 123456789 1000`", parse_mode=ParseMode.MARKDOWN); return
    try:
        target = int(args[0]); amount = int(args[1])
        if amount <= 0 or amount > 1000000: raise ValueError
    except: await update.message.reply_text("❌ Invalid numbers (1-1000000)."); return
    update_credits(target, amount)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE users SET total_gifted = total_gifted + ? WHERE user_id=?", (amount, target))
    if c.rowcount == 0: c.execute("INSERT INTO users (user_id, credits, total_gifted) VALUES (?, ?, ?)", (target, amount, amount))
    conn.commit(); conn.close()
    await update.message.reply_text("🎁 *GIFT SENT*\nTo: `" + str(target) + "`\nCredits: +" + str(amount), parse_mode=ParseMode.MARKDOWN)
    try:
        await ctx.bot.send_message(target, "🎁 *You received a gift!*\n+" + str(amount) + " credits!\nUse /balance.", parse_mode=ParseMode.MARKDOWN)
    except: pass

async def gencoupon_cmd(update, ctx):
    uid = update.effective_user.id
    if not is_owner(uid): await update.message.reply_text("⛔ Owner only."); return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Usage: `/gencoupon <credits> <max_uses> [CODE]`\nExample: `/gencoupon 500 10 WELCOME500`", parse_mode=ParseMode.MARKDOWN); return
    try: credits = int(args[0]); max_uses = int(args[1])
    except: await update.message.reply_text("❌ Invalid numbers."); return
    code = args[2].upper() if len(args) >= 3 else gen_code(10)
    add_coupon(code, credits, max_uses, uid)
    await update.message.reply_text("🎟️ *COUPON CREATED*\n\nCode: `" + code + "`\nCredits: " + str(credits) + "\nMax Uses: " + str(max_uses), parse_mode=ParseMode.MARKDOWN)

async def addkey_cmd(update, ctx):
    uid = update.effective_user.id
    if not is_owner(uid): await update.message.reply_text("⛔ Owner only."); return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Usage: `/addkey <credits> <max_uses>`", parse_mode=ParseMode.MARKDOWN); return
    try: credits = int(args[0]); max_uses = int(args[1])
    except: await update.message.reply_text("❌ Invalid."); return
    k = gen_code()
    add_key(k, credits, max_uses, uid)
    await update.message.reply_text("🔑 Key: `" + k + "`\nCredits: " + str(credits) + " | Max: " + str(max_uses), parse_mode=ParseMode.MARKDOWN)

async def addcredits_cmd(update, ctx):
    uid = update.effective_user.id
    if not is_owner(uid): await update.message.reply_text("⛔ Owner only."); return
    args = ctx.args
    if len(args) < 2: await update.message.reply_text("Usage: `/addcredits <user_id> <amount>`", parse_mode=ParseMode.MARKDOWN); return
    try: target = int(args[0]); amount = int(args[1])
    except: await update.message.reply_text("❌ Invalid."); return
    update_credits(target, amount)
    await update.message.reply_text("✅ Added " + str(amount) + " credits to `" + str(target) + "`", parse_mode=ParseMode.MARKDOWN)

async def stats_cmd(update, ctx):
    uid = update.effective_user.id
    if not is_owner(uid): await update.message.reply_text("⛔ Owner only."); return
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users"); tu = c.fetchone()[0]
    c.execute("SELECT SUM(credits) FROM users"); tc = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM jobs"); tj = c.fetchone()[0]
    c.execute("SELECT SUM(success_count) FROM jobs"); ts = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM coupons"); cp = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM keys"); kk = c.fetchone()[0]
    conn.close()
    await update.message.reply_text("📊 *BOT STATS*\n\n👥 Users: " + str(tu) + "\n💰 Credits: " + str(tc) + "\n💣 Jobs: " + str(tj) + "\n📨 SMS: " + str(ts) + "\n🎟️ Coupons: " + str(cp) + "\n🔑 Keys: " + str(kk), parse_mode=ParseMode.MARKDOWN)

async def broadcast_cmd(update, ctx):
    uid = update.effective_user.id
    if not is_owner(uid): await update.message.reply_text("⛔ Owner only."); return
    msg = update.message.text.replace("/broadcast", "").strip()
    if not msg: await update.message.reply_text("Usage: `/broadcast <msg>`", parse_mode=ParseMode.MARKDOWN); return
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT user_id FROM users"); uids = [r[0] for r in c.fetchall()]; conn.close()
    sent, fail = 0, 0
    for u in uids:
        try: await ctx.bot.send_message(u, msg); sent += 1; await asyncio.sleep(0.05)
        except: fail += 1
    await update.message.reply_text("📢 Sent: " + str(sent) + " | Failed: " + str(fail))

(TARGET, MESSAGE, COUNT, SPEED) = range(4)
(REDEEM_KEY, REDEEM_COUPON) = range(10, 12)

async def bomb_start(update, ctx):
    uid = update.effective_user.id
    cred_disp = "UNLIMITED" if is_owner(uid) else str(get_user_credits(uid))
    await update.message.reply_text("📞 Enter target (country code, e.g. 919876543210):\n💳 Balance: " + cred_disp + "\n/cancel to abort")
    return TARGET

async def bomb_target(update, ctx):
    t = update.message.text.strip()
    if t in ALL_BTNS: ctx.user_data.clear(); await button_router(update, ctx); return ConversationHandler.END
    if not t.lstrip("+").isdigit() or len(t) < 10:
        await update.message.reply_text("❌ Valid phone number daalo."); return TARGET
    ctx.user_data["target"] = t.lstrip("+")
    await update.message.reply_text("✏️ Message likho:")
    return MESSAGE

async def bomb_message(update, ctx):
    t = update.message.text
    if t in ALL_BTNS: ctx.user_data.clear(); await button_router(update, ctx); return ConversationHandler.END
    ctx.user_data["message"] = t
    uid = update.effective_user.id
    cred_disp = "UNLIMITED" if is_owner(uid) else str(get_user_credits(uid))
    await update.message.reply_text("📨 Kitne SMS?\n💰 Balance: *" + cred_disp + "*", parse_mode=ParseMode.MARKDOWN)
    return COUNT

async def bomb_count(update, ctx):
    t = update.message.text
    if t in ALL_BTNS: ctx.user_data.clear(); await button_router(update, ctx); return ConversationHandler.END
    try:
        n = int(t)
        if n <= 0: raise ValueError
        if n > MAX_PER_JOB: await update.message.reply_text("⚠️ Max " + str(MAX_PER_JOB)); return COUNT
    except: await update.message.reply_text("❌ Positive integer."); return COUNT
    uid = update.effective_user.id
    if not is_owner(uid) and n > get_user_credits(uid):
        await update.message.reply_text("⚠️ Sirf " + str(get_user_credits(uid)) + " credits. Redeem karo ya kam daalo."); return COUNT
    ctx.user_data["count"] = n
    kb = [[InlineKeyboardButton("🐢 Slow", callback_data="sp_slow")], [InlineKeyboardButton("🐇 Medium", callback_data="sp_med")], [InlineKeyboardButton("🚀 Fast", callback_data="sp_fast")]]
    await update.message.reply_text("⚡ Speed:", reply_markup=InlineKeyboardMarkup(kb))
    return SPEED

async def bomb_speed(update, ctx):
    q = update.callback_query; await q.answer()
    delay = {"sp_slow": 1.0, "sp_med": 0.5, "sp_fast": 0.1}.get(q.data, 0.5)
    uid = q.from_user.id
    target = ctx.user_data.get("target"); message = ctx.user_data.get("message"); count = ctx.user_data.get("count", 0)
    if not target or not message or count <= 0:
        await q.message.reply_text("❌ Data missing. /start"); return ConversationHandler.END
    if not deduct_credits(uid, count):
        await q.message.reply_text("❌ Insufficient credits."); return ConversationHandler.END
    job_id = str(uuid4())[:8]
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT INTO jobs (id, target, message, status, total_sms, user_id, chat_id) VALUES (?,?,?,?,?,?,?)", (job_id, target, message, "running", count, uid, q.message.chat_id))
    conn.commit(); conn.close()
    await q.message.reply_text("✅ Job launched!\n🆔 `" + job_id + "`\n📞 `" + target + "`\n📨 " + str(count), parse_mode=ParseMode.MARKDOWN)
    asyncio.create_task(_run_bomb(job_id, target, count, delay, uid, q.message.chat_id))
    ctx.user_data.clear()
    return ConversationHandler.END

async def _run_bomb(job_id, target, count, delay, uid, chat_id):
    apis = []
    if os.path.exists("data/sms_apis.json"):
        try:
            with open("data/sms_apis.json") as f: apis = json.load(f)
        except: apis = []
    success, fail = 0, 0
    msg_id = None
    for i in range(count):
        ok = False
        if apis:
            api = random.choice(apis)
            try:
                url = api["url"]; headers = api.get("headers", {})
                body = {k: str(v).replace("{phone}", target) for k, v in api.get("body", {}).items()}
                async with httpx.AsyncClient(timeout=10, verify=False) as cli:
                    if api.get("method", "POST") == "POST": r = await cli.post(url, headers=headers, json=body)
                    else: r = await cli.get(url, headers=headers)
                    ok = 200 <= r.status_code < 300
            except: ok = False
        else: ok = True
        if ok: success += 1
        else: fail += 1
        pct = int((i + 1) / count * 100); bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        text = "💣 `" + job_id + "`\n📞 `" + target + "`\n" + bar + " " + str(pct) + "%\n✅ " + str(success) + " | ❌ " + str(fail)
        try:
            if msg_id: await _BOT.edit_message_text(text, chat_id=chat_id, message_id=msg_id, parse_mode=ParseMode.MARKDOWN)
            else: m = await _BOT.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN); msg_id = m.message_id
        except: pass
        await asyncio.sleep(delay)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE jobs SET status='completed', success_count=?, fail_count=?, credit_used=? WHERE id=?", (success, fail, success, job_id))
    conn.commit(); conn.close()
    if fail > 0 and not is_owner(uid): update_credits(uid, fail)
    try: await _BOT.send_message(chat_id, "✅ *Complete!*\nJob: `" + job_id + "`\n✅ " + str(success) + " | ❌ " + str(fail), parse_mode=ParseMode.MARKDOWN)
    except: pass

async def cancel_conv(update, ctx):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

async def redeem_key_start(update, ctx):
    await update.message.reply_text("🔑 Key bhejo:\n/cancel to abort")
    return REDEEM_KEY

async def redeem_key_input(update, ctx):
    uid = update.effective_user.id; t = update.message.text.strip()
    if t in ALL_BTNS: ctx.user_data.clear(); await button_router(update, ctx); return ConversationHandler.END
    credits = redeem_code(t.upper(), uid, "key")
    if credits: await update.message.reply_text("✅ Key redeemed! +" + str(credits) + "\n💰 Balance: *" + str(get_user_credits(uid)) + "*", parse_mode=ParseMode.MARKDOWN)
    else: await update.message.reply_text("❌ Invalid key.")
    return ConversationHandler.END

async def redeem_coupon_start(update, ctx):
    await update.message.reply_text("🎟️ Coupon code bhejo:\n/cancel to abort")
    return REDEEM_COUPON

async def redeem_coupon_input(update, ctx):
    uid = update.effective_user.id; t = update.message.text.strip()
    if t in ALL_BTNS: ctx.user_data.clear(); await button_router(update, ctx); return ConversationHandler.END
    credits = redeem_code(t.upper(), uid, "coupon")
    if credits: await update.message.reply_text("🎟️ Coupon redeemed! +" + str(credits) + "\n💰 Balance: *" + str(get_user_credits(uid)) + "*", parse_mode=ParseMode.MARKDOWN)
    else: await update.message.reply_text("❌ Invalid coupon.")
    return ConversationHandler.END

async def button_router(update, ctx):
    text = update.message.text; uid = update.effective_user.id
    if text == BTN_BOMB: return await bomb_start(update, ctx)
    elif text == BTN_BAL: await balance_cmd(update, ctx)
    elif text == BTN_HIST: await history_cmd(update, ctx)
    elif text == BTN_STATUS: await status_cmd(update, ctx)
    elif text == BTN_REDEEM: return await redeem_key_start(update, ctx)
    elif text == BTN_COUPON: return await redeem_coupon_start(update, ctx)
    elif text == BTN_PREMIUM: await premium_menu(update, ctx)
    elif text == BTN_GIFT and is_owner(uid): await update.message.reply_text("🎁 Usage: `/gift <user_id> <credits>`", parse_mode=ParseMode.MARKDOWN)
    elif text == BTN_GENKEY and is_owner(uid): await update.message.reply_text("🔑 Usage: `/addkey <credits> <max_uses>`", parse_mode=ParseMode.MARKDOWN)
    elif text == BTN_GENCOUPON and is_owner(uid): await update.message.reply_text("🎟️ Usage: `/gencoupon <credits> <max_uses> [CODE]`", parse_mode=ParseMode.MARKDOWN)
    elif text == BTN_STATS and is_owner(uid): await stats_cmd(update, ctx)

_BOT = None

def main():
    global _BOT
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN missing in .env"); sys.exit(1)
    app = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()
    _BOT = app.bot

    bomb_conv = ConversationHandler(
        entry_points=[CommandHandler("bomb", bomb_start), MessageHandler(filters.Regex("^" + re.escape(BTN_BOMB) + "$"), bomb_start)],
        states={
            TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, bomb_target)],
            MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bomb_message)],
            COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bomb_count)],
            SPEED: [CallbackQueryHandler(bomb_speed, pattern="^sp_(slow|med|fast)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)], allow_reentry=True,
    )
    key_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^" + re.escape(BTN_REDEEM) + "$"), redeem_key_start)],
        states={REDEEM_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, redeem_key_input)]},
        fallbacks=[CommandHandler("cancel", cancel_conv)], allow_reentry=True,
    )
    coupon_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^" + re.escape(BTN_COUPON) + "$"), redeem_coupon_start)],
        states={REDEEM_COUPON: [MessageHandler(filters.TEXT & ~filters.COMMAND, redeem_coupon_input)]},
        fallbacks=[CommandHandler("cancel", cancel_conv)], allow_reentry=True,
    )

    app.add_handler(bomb_conv)
    app.add_handler(key_conv)
    app.add_handler(coupon_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("addkey", addkey_cmd))
    app.add_handler(CommandHandler("gencoupon", gencoupon_cmd))
    app.add_handler(CommandHandler("addcredits", addcredits_cmd))
    app.add_handler(CommandHandler("gift", gift_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("premium", premium_menu))
    app.add_handler(CommandHandler("freetrial", freetrial_cmd))
    app.add_handler(CallbackQueryHandler(claim_free_cb, pattern="^claim_free$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_router))

    logger.info("✅ Premium Bot v2 Started! Owner unlimited + Gift + Coupon + Premium")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
