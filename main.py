import os
import json
import logging
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Load .env values
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

DATA_FILE = "data.json"
MAX_CHANNELS = 5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load admin & channel data
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"admins": [], "channels": {}}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ===================== HANDLERS =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_owner = user_id == OWNER_ID
    is_admin = user_id in data["admins"]

    if is_owner or is_admin:
        keyboard = [
            [KeyboardButton("➕ Add Channel"), KeyboardButton("📤 Post")],
            [KeyboardButton("📋 My Channels"), KeyboardButton("🗑️ Remove Channel")],
        ]
        if is_owner:
            keyboard.append([KeyboardButton("➕ Add Admin")])
        await update.message.reply_text(
            "👋 Welcome Admin!",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
    else:
        await update.message.reply_text("❌ You are not authorized to use this bot.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_owner = user_id == OWNER_ID
    is_admin = user_id in data["admins"]

    if not (is_owner or is_admin):
        await update.message.reply_text("❌ Unauthorized.")
        return

    text = update.message.text
    state = context.user_data.get("state")

    if text == "➕ Add Admin" and is_owner:
        context.user_data["state"] = "adding_admin"
        await update.message.reply_text("👤 Send user ID to add as admin:")

    elif text == "➕ Add Channel":
        context.user_data["state"] = "adding_channel"
        await update.message.reply_text("🔗 Send @username or ID of the channel:")

    elif text == "📋 My Channels":
        channels = data["channels"].get(str(user_id), [])
        if not channels:
            await update.message.reply_text("📭 No channels added.")
        else:
            msg = "\n".join([f"{i+1}. `{ch}`" for i, ch in enumerate(channels)])
            await update.message.reply_text(f"📋 Your Channels:\n{msg}", parse_mode="Markdown")

    elif text == "🗑️ Remove Channel":
        channels = data["channels"].get(str(user_id), [])
        if not channels:
            await update.message.reply_text("❌ No channels to remove.")
        else:
            buttons = [
                [InlineKeyboardButton(f"❌ {ch}", callback_data=f"remove|{ch}")]
                for ch in channels
            ]
            await update.message.reply_text("Select a channel to remove:", reply_markup=InlineKeyboardMarkup(buttons))
            context.user_data["state"] = None

    elif text == "📤 Post":
        context.user_data["state"] = "awaiting_post"
        await update.message.reply_text("📝 Send message(s) to post.")

    elif state == "adding_admin" and is_owner:
        try:
            new_admin = int(text)
            if new_admin not in data["admins"]:
                data["admins"].append(new_admin)
                save_data()
                await update.message.reply_text("✅ Admin added.")
            else:
                await update.message.reply_text("⚠️ Already an admin.")
        except:
            await update.message.reply_text("❌ Invalid user ID.")
        context.user_data["state"] = None

    elif state == "adding_channel":
        ch_id = text.strip()
        try:
            chat = await context.bot.get_chat(ch_id)
            bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
            if bot_member.status != "administrator":
                await update.message.reply_text("⚠️ Bot is not admin in that channel.")
                return
            user_channels = data["channels"].get(str(user_id), [])
            if len(user_channels) >= MAX_CHANNELS:
                await update.message.reply_text(f"⚠️ Max {MAX_CHANNELS} channels allowed.")
                return
            if chat.id not in user_channels:
                user_channels.append(chat.id)
                data["channels"][str(user_id)] = user_channels
                save_data()
                await update.message.reply_text("✅ Channel added.")
            else:
                await update.message.reply_text("⚠️ Channel already added.")
        except Exception as e:
            await update.message.reply_text("❌ Failed to add channel.")
            logger.error(f"Add channel error: {e}")
        context.user_data["state"] = None

    else:
        await update.message.reply_text("❓ Unknown command.")

async def handle_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID and user_id not in data["admins"]:
        return
    batch = context.user_data.setdefault("forwarded_batch", [])
    batch.append(update.message)
    if len(batch) == 1:
        buttons = [
            [InlineKeyboardButton("✅ Post to All", callback_data="post_all")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_post")]
        ]
        await update.message.reply_text("Post to which channels?", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data_key = str(user_id)

    if query.data.startswith("remove|"):
        ch = query.data.split("|")[1]
        if ch in data["channels"].get(data_key, []):
            data["channels"][data_key].remove(ch)
            save_data()
            await query.edit_message_text(f"✅ Removed `{ch}`", parse_mode="Markdown")

    elif query.data == "post_all":
        messages = context.user_data.get("forwarded_batch", [])
        channels = data["channels"].get(data_key, [])
        for ch in channels:
            for msg in messages:
                try:
                    await forward_cleaned(msg, context, ch)
                except Exception as e:
                    logger.error(f"Post error: {e}")
        await query.edit_message_text("✅ Posted to all channels.")
        context.user_data.clear()

    elif query.data == "cancel_post":
        context.user_data.clear()
        await query.edit_message_text("❌ Cancelled.")

async def forward_cleaned(msg, context, ch_id):
    if msg.text:
        await context.bot.send_message(chat_id=ch_id, text=msg.text)
    elif msg.photo:
        await context.bot.send_photo(chat_id=ch_id, photo=msg.photo[-1].file_id, caption=msg.caption)
    elif msg.video:
        await context.bot.send_video(chat_id=ch_id, video=msg.video.file_id, caption=msg.caption)
    elif msg.document:
        await context.bot.send_document(chat_id=ch_id, document=msg.document.file_id, caption=msg.caption)

# ===================== MAIN =====================

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.FORWARDED, handle_forward))
    app.add_handler(MessageHandler(filters.TEXT, handle_text))
    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
