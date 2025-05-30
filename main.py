import json, os, logging
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

BOT_TOKEN = "YOUR_BOT_TOKEN"
DATA_FILE = "admin_data.json"
MAX_CHANNELS = 5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load or create admin data
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"super_admin": 123456789, "admins": {}}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# =========================== COMMANDS ===========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id == str(data["super_admin"]):
        keyboard = [
            [KeyboardButton("➕ Add User"), KeyboardButton("🗑️ Remove User")],
            [KeyboardButton("👥 My Admins")],
            [KeyboardButton("➕ Add Channel"), KeyboardButton("📤 Post to Channel")],
            [KeyboardButton("📋 My Channels"), KeyboardButton("🗑️ Remove Channel")],
        ]
    elif user_id in data["admins"]:
        keyboard = [
            [KeyboardButton("➕ Add Channel"), KeyboardButton("📤 Post to Channel")],
            [KeyboardButton("📋 My Channels"), KeyboardButton("🗑️ Remove Channel")],
        ]
    else:
        await update.message.reply_text("❌ You are not authorized.")
        return

    await update.message.reply_text("👋 Welcome! Choose an option:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

# ========================== ADMIN PANEL ==========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text
    state = context.user_data.get("state")

    # ================= SUPER ADMIN OPTIONS =================
    if user_id == str(data["super_admin"]):
        if text == "➕ Add User":
            context.user_data["state"] = "adding_user"
            await update.message.reply_text("👤 Send user ID to add as admin.")
            return

        elif text == "🗑️ Remove User":
            context.user_data["state"] = "removing_user"
            await update.message.reply_text("🗑️ Send user ID to remove from admins.")
            return

        elif text == "👥 My Admins":
            admins = "\n".join([f"- {uid}" for uid in data["admins"].keys()])
            await update.message.reply_text(f"👥 Admins:\n{admins or '❌ No admins yet.'}")
            return

    # Handle add/remove user
    if state == "adding_user":
        new_id = text.strip()
        if new_id in data["admins"]:
            await update.message.reply_text("⚠️ Already an admin.")
        else:
            data["admins"][new_id] = []
            save_data()
            await update.message.reply_text("✅ User added as admin.")
        context.user_data.pop("state", None)
        return

    elif state == "removing_user":
        remove_id = text.strip()
        if remove_id in data["admins"]:
            del data["admins"][remove_id]
            save_data()
            await update.message.reply_text("✅ User removed.")
        else:
            await update.message.reply_text("⚠️ Not found.")
        context.user_data.pop("state", None)
        return

    # ================= ADMIN OPTIONS =================

    if user_id not in data["admins"] and user_id != str(data["super_admin"]):
        await update.message.reply_text("❌ Not authorized.")
        return

    # Channel operations
    if text == "➕ Add Channel":
        context.user_data["state"] = "adding_channel"
        await update.message.reply_text("🔗 Send channel @username or ID to add.")
    elif text == "📋 My Channels":
        channels = data["admins"].get(user_id, [])
        if not channels:
            await update.message.reply_text("📭 No channels added.")
        else:
            await update.message.reply_text("📋 Your Channels:\n" + "\n".join(channels))
    elif text == "🗑️ Remove Channel":
        channels = data["admins"].get(user_id, [])
        if not channels:
            await update.message.reply_text("📭 No channels to remove.")
        else:
            buttons = [[InlineKeyboardButton(ch, callback_data=f"remove|{ch}")] for ch in channels]
            await update.message.reply_text("🗑️ Select channel to remove:", reply_markup=InlineKeyboardMarkup(buttons))
    elif text == "📤 Post to Channel":
        context.user_data["state"] = "awaiting_post"
        context.user_data["messages"] = []
        await update.message.reply_text("📝 Send messages to post.")
    elif state == "adding_channel":
        new = text.strip()
        if len(data["admins"][user_id]) >= MAX_CHANNELS:
            await update.message.reply_text(f"⚠️ Max {MAX_CHANNELS} channels allowed.")
        else:
            data["admins"][user_id].append(new)
            save_data()
            await update.message.reply_text("✅ Channel added.")
        context.user_data.pop("state", None)
    elif state == "awaiting_post":
        context.user_data["messages"].append(update.message)
        buttons = [
            [InlineKeyboardButton("✅ Post to All", callback_data="post_all")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_post")],
        ]
        await update.message.reply_text("📤 Ready to post?", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text("❓ Unknown command.")

# ========================== CALLBACKS ===========================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()

    if "remove|" in query.data:
        _, ch = query.data.split("|")
        if ch in data["admins"].get(user_id, []):
            data["admins"][user_id].remove(ch)
            save_data()
            await query.edit_message_text(f"✅ Removed {ch}")
        return

    if query.data == "cancel_post":
        context.user_data.clear()
        await query.edit_message_text("❌ Post cancelled.")
    elif query.data == "post_all":
        msgs = context.user_data.get("messages", [])
        channels = data["admins"].get(user_id, [])
        for ch in channels:
            for msg in msgs:
                try:
                    await forward_cleaned(msg, context, ch)
                except Exception as e:
                    logger.warning(f"Post fail: {e}")
        await query.edit_message_text("✅ Posted to all channels.")
        context.user_data.clear()

# ========================== CLEAN FORWARD ===========================

async def forward_cleaned(message, context, chat_id):
    if message.text:
        await context.bot.send_message(chat_id=chat_id, text=message.text)
    elif message.photo:
        await context.bot.send_photo(chat_id=chat_id, photo=message.photo[-1].file_id, caption=message.caption)
    elif message.video:
        await context.bot.send_video(chat_id=chat_id, video=message.video.file_id, caption=message.caption)
    elif message.document:
        await context.bot.send_document(chat_id=chat_id, document=message.document.file_id, caption=message.caption)

# =========================== MAIN ===========================

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    print("✅ Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
