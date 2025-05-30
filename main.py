import json
import os
import logging
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
)

# Get the bot token securely from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Admin Telegram user IDs (int list)
ADMIN_IDS = [8150652959]

# JSON file to store user channels
DATA_FILE = "user_channels.json"
MAX_CHANNELS = 5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load or initialize user channels
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        user_channels = json.load(f)
else:
    user_channels = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(user_channels, f)

# ============================= HANDLERS =============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS:
        keyboard = [
            [KeyboardButton("➕ Add Channel"), KeyboardButton("📤 Post to Channel")],
            [KeyboardButton("📋 My Channels"), KeyboardButton("🗑️ Remove Channel")],
        ]
        await update.message.reply_text(
            "👋 Welcome Admin! Choose an option:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
    else:
        await update.message.reply_text("❌ This bot is for admins only.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return

    text = update.message.text
    state = context.user_data.get("state")

    if text == "➕ Add Channel":
        context.user_data["state"] = "adding"
        await update.message.reply_text(
            "🔗 Send @username or ID of the channel(s) to add (max 5).",
            reply_markup=ReplyKeyboardRemove()
        )

    elif text == "📋 My Channels":
        channels = user_channels.get(str(user_id), [])
        if not channels:
            await update.message.reply_text("❌ You haven't added any channels.")
        else:
            msg = ""
            for i, ch_id in enumerate(channels):
                try:
                    chat = await context.bot.get_chat(ch_id)
                    name = chat.title or chat.username or str(chat.id)
                    msg += f"{i+1}. {name} (`{ch_id}`)\n"
                except Exception as e:
                    msg += f"{i+1}. ⚠️ Failed to fetch name for `{ch_id}`\n"
            await update.message.reply_text(f"📋 Your Channels:\n{msg}", parse_mode="Markdown")

    elif text == "🗑️ Remove Channel":
        channels = user_channels.get(str(user_id), [])
        if not channels:
            await update.message.reply_text("❌ No channels to remove.")
            return
        context.user_data["state"] = "removing"
        buttons = [[InlineKeyboardButton(f"❌ {ch}", callback_data=f"confirm_remove|{ch}")] for ch in channels]
        await update.message.reply_text("🗑️ Select a channel to remove:", reply_markup=InlineKeyboardMarkup(buttons))

    elif text == "📤 Post to Channel":
        context.user_data["state"] = "awaiting_post"
        context.user_data["forwarded_batch"] = []
        await update.message.reply_text("📝 Send the message(s) you want to post.")

    elif state == "adding":
        new_channels = text.strip().split()
        valid_channels = []

        for ch in new_channels:
            try:
                chat = await context.bot.get_chat(ch)
                bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
                if bot_member.status != "administrator":
                    continue
                valid_channels.append(str(chat.id))
            except Exception as e:
                logger.warning(f"Failed to add channel {ch}: {e}")

        existing = user_channels.get(str(user_id), [])
        if len(existing) + len(valid_channels) > MAX_CHANNELS:
            await update.message.reply_text(f"⚠️ Cannot add more than {MAX_CHANNELS} channels.")
        else:
            user_channels[str(user_id)] = list(set(existing + valid_channels))
            save_data()
            await update.message.reply_text(f"✅ Added {len(valid_channels)} channel(s).")

        context.user_data.pop("state", None)

    else:
        await update.message.reply_text("❓ Unknown command. Use the menu buttons.")

async def handle_forwards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    batch = context.user_data.setdefault("forwarded_batch", [])
    batch.append(update.message)

    if len(batch) == 1:
        context.user_data["pending_post"] = batch
        buttons = [
            [InlineKeyboardButton("✅ Post to All", callback_data="post_all")],
            [InlineKeyboardButton("📂 Select Channels", callback_data="post_select")],
            [InlineKeyboardButton("❌ Cancel", callback_data="post_cancel")],
        ]
        await update.message.reply_text("📤 Where would you like to post these messages?", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith("confirm_remove"):
        _, ch = query.data.split("|")
        channels = user_channels.get(str(user_id), [])
        if ch in channels:
            channels.remove(ch)
            user_channels[str(user_id)] = channels
            save_data()
            await query.edit_message_text(f"✅ Removed `{ch}`", parse_mode="Markdown")

    elif query.data == "post_cancel":
        await query.edit_message_text("❌ Post cancelled.")
        context.user_data.pop("pending_post", None)
        context.user_data.pop("forwarded_batch", None)

    elif query.data == "post_all":
        messages = context.user_data.get("pending_post", [])
        channels = user_channels.get(str(user_id), [])
        for msg in messages:
            for ch in channels:
                try:
                    await forward_cleaned(msg, context, ch)
                except Exception as e:
                    logger.warning(f"Failed to post to {ch}: {e}")
        await query.edit_message_text("✅ Posted to all channels.")
        context.user_data.clear()

    elif query.data == "post_select":
        channels = user_channels.get(str(user_id), [])
        buttons = [[InlineKeyboardButton(ch, callback_data=f"do_post|{ch}")] for ch in channels]
        buttons.append([InlineKeyboardButton("❌ Done", callback_data="done_post")])
        context.user_data["selected_channels"] = []
        await query.edit_message_text("✅ Select channels to post to:", reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data.startswith("do_post"):
        _, ch = query.data.split("|")
        selected = context.user_data.setdefault("selected_channels", [])
        if ch not in selected:
            selected.append(ch)
        await query.answer(f"Selected: {ch}")

    elif query.data == "done_post":
        messages = context.user_data.get("pending_post", [])
        selected_channels = context.user_data.get("selected_channels", [])
        for msg in messages:
            for ch in selected_channels:
                try:
                    await forward_cleaned(msg, context, ch)
                except Exception as e:
                    logger.warning(f"Failed to post to {ch}: {e}")
        await query.edit_message_text("✅ Posted to selected channels.")
        context.user_data.clear()

# ============================= CLEAN FORWARD =============================

async def forward_cleaned(message, context, target_chat_id):
    if message.text:
        await context.bot.send_message(chat_id=target_chat_id, text=message.text)
    elif message.photo:
        await context.bot.send_photo(chat_id=target_chat_id, photo=message.photo[-1].file_id, caption=message.caption)
    elif message.video:
        await context.bot.send_video(chat_id=target_chat_id, video=message.video.file_id, caption=message.caption)
    elif message.document:
        await context.bot.send_document(chat_id=target_chat_id, document=message.document.file_id, caption=message.caption)

# ============================= MAIN =============================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("❌ BOT_TOKEN environment variable is not set.")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.FORWARDED, handle_forwards))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_message))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
