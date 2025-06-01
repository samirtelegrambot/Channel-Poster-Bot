import json
import os
import logging
import sqlite3
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ExtBot,
)
from telegram.error import TelegramError
from dotenv import load_dotenv
import asyncio
import aiohttp

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
MAX_CHANNELS = 5
PORT = int(os.getenv("PORT", 8443))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g., https://your-render-app.onrender.com

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# SQLite Database Setup
def init_db():
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS user_channels (
            user_id INTEGER,
            channel_id TEXT,
            PRIMARY KEY (user_id, channel_id)
        )"""
    )
    conn.commit()
    return conn

# Database Operations
def load_admins(conn):
    c = conn.cursor()
    c.execute("SELECT user_id FROM admins")
    return [row[0] for row in c.fetchall()]

def save_admin(conn, admin_id):
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))
    conn.commit()

def remove_admin(conn, admin_id):
    c = conn.cursor()
    c.execute("DELETE FROM admins WHERE user_id = ?", (admin_id,))
    conn.commit()

def load_user_channels(conn, user_id):
    c = conn.cursor()
    c.execute("SELECT channel_id FROM user_channels WHERE user_id = ?", (user_id,))
    return [row[0] for row in c.fetchall()]

def save_user_channel(conn, user_id, channel_id):
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO user_channels (user_id, channel_id) VALUES (?, ?)",
        (user_id, channel_id),
    )
    conn.commit()

def remove_user_channel(conn, user_id, channel_id):
    c = conn.cursor()
    c.execute(
        "DELETE FROM user_channels WHERE user_id = ? AND channel_id = ?",
        (user_id, channel_id),
    )
    conn.commit()

# Initialize Database and Load Data
conn = init_db()
admins = load_admins(conn)
if OWNER_ID not in admins:
    admins.append(OWNER_ID)
    save_admin(conn, OWNER_ID)

# Rate Limiting
RATE_LIMIT = 20  # Max 20 messages per minute
user_message_timestamps = {}

async def check_rate_limit(user_id):
    import time
    current_time = time.time()
    timestamps = user_message_timestamps.get(user_id, [])
    timestamps = [t for t in timestamps if current_time - t < 60]  # Last minute
    timestamps.append(current_time)
    user_message_timestamps[user_id] = timestamps
    if len(timestamps) > RATE_LIMIT:
        return False
    return True

# Helper Functions
def get_main_menu_keyboard(user_id):
    keyboard = [
        [KeyboardButton("➕ Add Channel"), KeyboardButton("📤 Post to Channel")],
        [KeyboardButton("📋 My Channels"), KeyboardButton("🗑️ Remove Channel")],
    ]
    if user_id == OWNER_ID:
        keyboard.append([KeyboardButton("👥 Manage Admins")])
    return keyboard

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message="👋 Welcome! Choose an option:"):
    user_id = update.effective_user.id
    await update.message.reply_text(
        message,
        reply_markup=ReplyKeyboardMarkup(get_main_menu_keyboard(user_id), resize_keyboard=True),
    )

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/start used by user: {user_id}")
    if user_id not in admins:
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
    await send_main_menu(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins:
        await update.message.reply_text("❌ You are not authorized.")
        return

    if not await check_rate_limit(user_id):
        await update.message.reply_text("⚠️ You're sending messages too quickly. Please wait a moment.")
        return

    text = update.message.text
    state = context.user_data.get("state")

    if text == "❌ Cancel":
        context.user_data.clear()
        await send_main_menu(update, context, "❌ Operation cancelled. Choose an option:")
        return

    if text == "➕ Add Channel":
        context.user_data["state"] = "adding"
        keyboard = [[KeyboardButton("❌ Cancel")]]
        await update.message.reply_text(
            "🔗 Send @username or ID of the channel(s) to add (max 5).",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

    elif text == "📋 My Channels":
        channels = load_user_channels(conn, user_id)
        if not channels:
            await update.message.reply_text("❌ You haven't added any channels.")
        else:
            msg = ""
            for i, ch_id in enumerate(channels):
                try:
                    chat = await context.bot.get_chat(ch_id)
                    name = chat.title or chat.username or str(chat.id)
                    msg += f"{i+1}. {name} (`{ch_id}`)\n"
                except TelegramError as e:
                    logger.warning(f"Failed to fetch channel {ch_id}: {e}")
                    msg += f"{i+1}. ⚠️ Failed to fetch `{ch_id}`\n"
            await update.message.reply_text(f"📋 Your Channels:\n{msg}", parse_mode="Markdown")

    elif text == "🗑️ Remove Channel":
        channels = load_user_channels(conn, user_id)
        if not channels:
            await update.message.reply_text("❌ No channels to remove.")
            return
        context.user_data["state"] = "removing"
        buttons = [[InlineKeyboardButton(f"❌ {ch}", callback_data=f"confirm_remove|{ch}")] for ch in channels]
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        await update.message.reply_text(
            "🗑️ Select a channel to remove:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    elif text == "📤 Post to Channel":
        context.user_data["state"] = "awaiting_post"
        context.user_data["forwarded_batch"] = []
        context.user_data["pending_post"] = []
        keyboard = [[KeyboardButton("❌ Cancel")]]
        await update.message.reply_text(
            "📝 Send the message(s) you want to post.",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

    elif text == "👥 Manage Admins" and user_id == OWNER_ID:
        keyboard = [
            [KeyboardButton("➕ Add Admin"), KeyboardButton("🗑️ Remove Admins")],
            [KeyboardButton("📋 List Admins"), KeyboardButton("⬅️ Back")],
        ]
        await update.message.reply_text(
            "👥 Manage Admins Menu - Choose an option:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

    elif text == "➕ Add Admin" and user_id == OWNER_ID:
        context.user_data["state"] = "adding_admin"
        keyboard = [[KeyboardButton("❌ Cancel")]]
        await update.message.reply_text(
            "👤 Send the Telegram ID of the new admin:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

    elif text == "🗑️ Remove Admins" and user_id == OWNER_ID:
        if len(admins) <= 1:
            await update.message.reply_text("❌ No admins to remove (only the owner remains).")
            return
        context.user_data["state"] = "removing_admin"
        buttons = [
            [InlineKeyboardButton(f"❌ {admin_id}", callback_data=f"confirm_remove_admin|{admin_id}")]
            for admin_id in admins if admin_id != OWNER_ID
        ]
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        await update.message.reply_text(
            "🗑️ Select an admin to remove:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    elif text == "📋 List Admins" and user_id == OWNER_ID:
        if not admins:
            await update.message.reply_text("❌ No admins found.")
        else:
            msg = "👥 Admins:\n"
            for i, admin_id in enumerate(admins):
                msg += f"{i+1}. `{admin_id}` {'(Owner)' if admin_id == OWNER_ID else ''}\n"
            await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "⬅️ Back" and user_id in admins:
        await send_main_menu(update, context)

    elif text == "✅ Post to All" and context.user_data.get("pending_post"):
        messages = context.user_data.get("pending_post", [])
        channels = load_user_channels(conn, user_id)
        for msg in messages:
            for ch in channels:
                try:
                    await forward_cleaned(msg, context, ch)
                except TelegramError as e:
                    logger.warning(f"Failed to post to {ch}: {e}")
        await update.message.reply_text("✅ Posted to all channels.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()

    elif text == "📂 Select Channels" and context.user_data.get("pending_post"):
        channels = load_user_channels(conn, user_id)
        if not channels:
            await update.message.reply_text("❌ No channels available.")
            context.user_data.clear()
            return
        context.user_data["state"] = "selecting_channels"
        context.user_data["selected_channels"] = []
        keyboard = [[KeyboardButton(ch)] for ch in channels]
        keyboard.append([KeyboardButton("✅ Done"), KeyboardButton("❌ Cancel")])
        await update.message.reply_text(
            "✅ Select channels to post to:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True),
        )

    elif state == "selecting_channels":
        if text == "✅ Done":
            messages = context.user_data.get("pending_post", [])
            selected_channels = context.user_data.get("selected_channels", [])
            if not selected_channels:
                await update.message.reply_text("❌ No channels selected.")
            else:
                for msg in messages:
                    for ch in selected_channels:
                        try:
                            await forward_cleaned(msg, context, ch)
                        except TelegramError as e:
                            logger.warning(f"Failed to post to {ch}: {e}")
                await update.message.reply_text("✅ Posted to selected channels.", reply_markup=ReplyKeyboardRemove())
            context.user_data.clear()
            await send_main_menu(update, context)
        else:
            channels = load_user_channels(conn, user_id)
            if text in channels:
                selected = context.user_data.setdefault("selected_channels", [])
                if text not in selected:
                    selected.append(text)
                    await update.message.reply_text(f"✅ Selected: {text}")
                else:
                    await update.message.reply_text(f"⚠️ {text} already selected.")
            else:
                await update.message.reply_text("❌ Invalid channel.")

    elif state == "adding":
        new_channels = text.strip().split()
        if not new_channels:
            await update.message.reply_text("❌ Please provide at least one channel.")
            return
        valid_channels = []
        for ch in new_channels:
            try:
                chat = await context.bot.get_chat(ch)
                bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
                if bot_member.status != "administrator":
                    await update.message.reply_text(f"⚠️ I need to be an admin in {ch} to add it.")
                    continue
                valid_channels.append(str(chat.id))
            except TelegramError as e:
                logger.warning(f"Failed to add channel {ch}: {e}")
                await update.message.reply_text(f"❌ Failed to add {ch}: Invalid or inaccessible channel.")

        existing = load_user_channels(conn, user_id)
        if len(existing) + len(valid_channels) > MAX_CHANNELS:
            await update.message.reply_text(f"⚠️ Max {MAX_CHANNELS} channels allowed.")
        else:
            for ch_id in valid_channels:
                save_user_channel(conn, user_id, ch_id)
            await update.message.reply_text(f"✅ Added {len(valid_channels)} channel(s).")
        context.user_data.pop("state", None)
        await send_main_menu(update, context)

    elif state == "adding_admin" and user_id == OWNER_ID:
        try:
            new_admin_id = int(text.strip())
            if new_admin_id not in admins:
                admins.append(new_admin_id)
                save_admin(conn, new_admin_id)
                await update.message.reply_text(f"✅ Added new admin: `{new_admin_id}`", parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ Admin already exists.")
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID. Please enter a numeric Telegram ID.")
        context.user_data.pop("state", None)
        await send_main_menu(update, context)

    else:
        await send_main_menu(update, context, "❓ Unknown command. Please choose an option:")

async def handle_forwards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins:
        return

    if not await check_rate_limit(user_id):
        await update.message.reply_text("⚠️ You're sending messages too quickly. Please wait a moment.")
        return

    context.user_data.setdefault("pending_post", []).append(update.message)
    if len(context.user_data["pending_post"]) == 1:
        keyboard = [
            [KeyboardButton("✅ Post to All"), KeyboardButton("📂 Select Channels")],
            [KeyboardButton("❌ Cancel")],
        ]
        await update.message.reply_text(
            "📤 Choose where to post:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ Operation cancelled.")
        await send_main_menu(update, context)
        return

    if query.data.startswith("confirm_remove"):
        _, ch = query.data.split("|")
        channels = load_user_channels(conn, user_id)
        if ch in channels:
            remove_user_channel(conn, user_id, ch)
            await query.edit_message_text(f"✅ Removed `{ch}`", parse_mode="Markdown")
        await send_main_menu(update, context)

    elif query.data.startswith("confirm_remove_admin"):
        _, admin_id = query.data.split("|")
        admin_id = int(admin_id)
        if admin_id in admins and admin_id != OWNER_ID:
            admins.remove(admin_id)
            remove_admin(conn, admin_id)
            await query.edit_message_text(f"✅ Removed admin: `{admin_id}`", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ Cannot remove the owner or invalid admin.")
        await send_main_menu(update, context)

async def forward_cleaned(message, context, target_chat_id):
    try:
        if message.text:
            await context.bot.send_message(chat_id=target_chat_id, text=message.text)
        elif message.photo:
            await context.bot.send_photo(
                chat_id=target_chat_id, photo=message.photo[-1].file_id, caption=message.caption
            )
        elif message.video:
            await context.bot.send_video(
                chat_id=target_chat_id, video=message.video.file_id, caption=message.caption
            )
        elif message.document:
            await context.bot.send_document(
                chat_id=target_chat_id, document=message.document.file_id, caption=message.caption
            )
    except TelegramError as e:
        logger.error(f"Error forwarding to {target_chat_id}: {e}")
        raise

# Webhook Setup
async def set_webhook(app: Application):
    webhook_url = f"{WEBHOOK_URL}/{BOT_TOKEN}"
    await app.bot.set_webhook(url=webhook_url)
    logger.info(f"Webhook set to {webhook_url}")

# Main
async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.FORWARDED, handle_forwards))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_message))

    await set_webhook(app)
    logger.info("Bot is running with webhook...")

    # Start the webhook server
    await app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
    )

if __name__ == "__main__":
    asyncio.run(main())
