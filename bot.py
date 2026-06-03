import os
import sqlite3
import logging
import requests
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("8893138368:AAGA5vlv9Z4KsOONdU9sdxXUCJL6Cvlf6wo")

ADMINS = {
    8411875335,
    6019893168
}

DB_NAME = "bot.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# =========================
# DATABASE
# =========================

def get_db():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        credits INTEGER DEFAULT 1,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS redeem_codes (
        code TEXT PRIMARY KEY,
        amount INTEGER,
        used INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()


def add_user(user):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO users
        (user_id, username, first_name, credits)
        VALUES (?, ?, ?, ?)
        """,
        (
            user.id,
            user.username,
            user.first_name,
            1
        )
    )

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user_id,)
    )

    data = cur.fetchone()
    conn.close()

    return data


def get_credits(user_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT credits FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cur.fetchone()
    conn.close()

    return row[0] if row else 0


def update_credits(user_id, amount):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE users
        SET credits = credits + ?
        WHERE user_id = ?
        """,
        (amount, user_id)
    )

    conn.commit()
    conn.close()


def total_users():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")

    count = cur.fetchone()[0]
    conn.close()

    return count


# =========================
# HELPERS
# =========================

def is_admin(user_id):
    return user_id in ADMINS


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user)

    keyboard = [
        [
            InlineKeyboardButton(
                "💰 My Points",
                callback_data="mypoints"
            )
        ],
        [
            InlineKeyboardButton(
                "🎁 Redeem",
                callback_data="redeem"
            )
        ]
    ]

    await update.message.reply_text(
        f"👋 Welcome {user.first_name}\n\n"
        f"You received 1 free credit.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# BUTTONS
# =========================

async def button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id

    if query.data == "mypoints":
        credits = get_credits(uid)

        await query.message.reply_text(
            f"💰 Credits: {credits}"
        )

    elif query.data == "redeem":
        await query.message.reply_text(
            "Use:\n/redeem CODE"
        )


# =========================
# MYPOINTS
# =========================

async def mypoints(update: Update, context):
    uid = update.effective_user.id

    credits = get_credits(uid)

    await update.message.reply_text(
        f"💰 Your Credits: {credits}"
    )


# =========================
# REDEEM
# =========================

async def redeem(update: Update, context):
    uid = update.effective_user.id

    if len(context.args) != 1:
        await update.message.reply_text(
            "Usage:\n/redeem CODE"
        )
        return

    code = context.args[0]

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT amount, used
        FROM redeem_codes
        WHERE code=?
        """,
        (code,)
    )

    row = cur.fetchone()

    if not row:
        conn.close()
        await update.message.reply_text("❌ Invalid code")
        return

    amount, used = row

    if used:
        conn.close()
        await update.message.reply_text("❌ Code already used")
        return

    cur.execute(
        "UPDATE redeem_codes SET used=1 WHERE code=?",
        (code,)
    )

    conn.commit()
    conn.close()

    update_credits(uid, amount)

    await update.message.reply_text(
        f"✅ Redeemed {amount} credits"
    )


# =========================
# CREATE CODE
# =========================

async def createcode(update: Update, context):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "/createcode CODE AMOUNT"
        )
        return

    code = context.args[0]
    amount = int(context.args[1])

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR REPLACE INTO redeem_codes
        (code, amount, used)
        VALUES (?, ?, 0)
        """,
        (code, amount)
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Code created\nCode: {code}\nAmount: {amount}"
    )


# =========================
# ADD CREDIT
# =========================

async def add(update: Update, context):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "/add USER_ID AMOUNT"
        )
        return

    uid = int(context.args[0])
    amount = int(context.args[1])

    update_credits(uid, amount)

    await update.message.reply_text(
        "✅ Credits added"
    )


# =========================
# USERINFO
# =========================

async def userinfo(update: Update, context):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) != 1:
        await update.message.reply_text(
            "/userinfo USER_ID"
        )
        return

    uid = int(context.args[0])

    data = get_user(uid)

    if not data:
        await update.message.reply_text(
            "User not found"
        )
        return

    await update.message.reply_text(
        f"ID: {data[0]}\n"
        f"Username: {data[1]}\n"
        f"Name: {data[2]}\n"
        f"Credits: {data[3]}"
    )


# =========================
# ALL USERS
# =========================

async def allusers(update: Update, context):
    if not is_admin(update.effective_user.id):
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT user_id, username, credits
        FROM users
        """
    )

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("No users")
        return

    text = "👥 Users:\n\n"

    for row in rows[:100]:
        text += (
            f"ID: {row[0]}\n"
            f"User: @{row[1]}\n"
            f"Credits: {row[2]}\n\n"
        )

    await update.message.reply_text(text)


# =========================
# TOTAL USERS
# =========================

async def num_count(update: Update, context):
    if len(context.args) == 0:
        await update.message.reply_text(
            f"👥 Total Users: {total_users()}"
        )
        return

    number = context.args[0]

    credits = get_credits(update.effective_user.id)

    if credits <= 0:
        await update.message.reply_text(
            "❌ No credits left"
        )
        return

    loading = await update.message.reply_text(
        "⏳ Fetching..."
    )

    try:
        url = (
            "https://api.subhxcosmo.in/api"
            "?key=CHX5"
            "&type=mobile"
            f"&term={number}"
        )

        response = requests.get(
            url,
            timeout=15
        )

        data = response.json()

        update_credits(
            update.effective_user.id,
            -1
        )

        await loading.edit_text(
            f"📱 Result:\n\n{data}"
        )

    except Exception as e:
        logger.error(e)

        await loading.edit_text(
            "❌ API Error"
        )


# =========================
# ERROR HANDLER
# =========================

async def error_handler(update, context):
    logger.error(
        msg="Exception",
        exc_info=context.error
    )


# =========================
# MAIN
# =========================

def main():
    init_db()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("mypoints", mypoints)
    )

    app.add_handler(
        CommandHandler("redeem", redeem)
    )

    app.add_handler(
        CommandHandler("num", num_count)
    )

    app.add_handler(
        CommandHandler("add", add)
    )

    app.add_handler(
        CommandHandler("createcode", createcode)
    )

    app.add_handler(
        CommandHandler("userinfo", userinfo)
    )

    app.add_handler(
        CommandHandler("allusers", allusers)
    )

    app.add_handler(
        CallbackQueryHandler(button_handler)
    )

    app.add_error_handler(error_handler)

    print("Bot Started...")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
