import json
import os
from telegram import (
    Update, KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes,
    ConversationHandler, filters
)
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 8150652959

ADMINS_FILE = 'admins.json'
CHANNELS_FILE = 'user_channels.json'

# Ensure data files exist
for file_name in [ADMINS_FILE, CHANNELS_FILE]:
    if not os.path.exists(file_name):
        with open(file_name, 'w') as f:
            json.dump({}, f)

def load_admins():
    with open(ADMINS_FILE) as f:
        return json.load(f)

def save_admins(data):
    with open(ADMINS_FILE, 'w') as f:
        json.dump(data, f)

def load_channels():
    with open(CHANNELS_FILE) as f:
        return json.load(f)

def save_channels(data):
    with open(CHANNELS_FILE, 'w') as f:
        json.dump(data, f)

def is_admin(user_id):
    admins = load_admins()
    return str(user_id) in admins or user_id == OWNER_ID

# Conversation states
ADD_ADMIN, REMOVE_ADMIN, ADD_CHANNEL, REMOVE_CHANNEL, AWAITING_POST_TEXT = range(5)

def get_main_keyboard(user_id):
    buttons = [
        [KeyboardButton("➕ Add Channel"), KeyboardButton("➖ Remove Channel")],
        [KeyboardButton("📋 My Channels"), KeyboardButton("📨 Post")]
    ]
    if user_id == OWNER_ID:
        buttons.append([KeyboardButton("👤 Manage Admins")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Access denied.")
        return
    await update.message.reply_text("Choose an option:", reply_markup=get_main_keyboard(user_id))

# Handle menu
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "➕ Add Channel":
        await update.message.reply_text("Send the @channel username to add:")
        return ADD_CHANNEL

    elif text == "➖ Remove Channel":
        await update.message.reply_text("Send the @channel username to remove:")
        return REMOVE_CHANNEL

    elif text == "📋 My Channels":
        channels = load_channels()
        user_channels = channels.get(str(user_id), [])
        msg = "Your channels:\n" + "\n".join(user_channels) if user_channels else "No channels added."
        await update.message.reply_text(msg, reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    elif text == "📨 Post":
        channels = load_channels()
        user_channels = channels.get(str(user_id), [])
        if not user_channels:
            await update.message.reply_text("You have no channels added.")
            return ConversationHandler.END
        buttons = [[InlineKeyboardButton(name, callback_data=f"post_to|{name}")] for name in user_channels]
        await update.message.reply_text("Select a channel:", reply_markup=InlineKeyboardMarkup(buttons))
        return ConversationHandler.END

    elif text == "👤 Manage Admins" and user_id == OWNER_ID:
        buttons = [
            [KeyboardButton("➕ Add Admin"), KeyboardButton("➖ Remove Admin")],
            [KeyboardButton("🔙 Back")]
        ]
        await update.message.reply_text("Admin management:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return ConversationHandler.END

    elif text == "➕ Add Admin" and user_id == OWNER_ID:
        await update.message.reply_text("Send the user ID to add as admin:")
        return ADD_ADMIN

    elif text == "➖ Remove Admin" and user_id == OWNER_ID:
        await update.message.reply_text("Send the user ID to remove:")
        return REMOVE_ADMIN

    elif text == "🔙 Back":
        await update.message.reply_text("Main menu:", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    else:
        await update.message.reply_text("⚠️ Please use the buttons below.")
        return ConversationHandler.END

# Add admin
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.text.strip()
    context.user_data["pending_admin_id"] = user_id
    await update.message.reply_text(
        f"Add user {user_id} as admin?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm", callback_data="confirm_add_admin"),
             InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ])
    )
    return ConversationHandler.END

# Remove admin
async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.text.strip()
    context.user_data["pending_admin_id"] = user_id
    await update.message.reply_text(
        f"Remove user {user_id} from admin?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm", callback_data="confirm_remove_admin"),
             InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ])
    )
    return ConversationHandler.END

# Add channel
async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel = update.message.text.strip()
    context.user_data["pending_channel"] = channel
    await update.message.reply_text(
        f"Add channel {channel}?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm", callback_data="confirm_add_channel"),
             InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ])
    )
    return ConversationHandler.END

# Remove channel
async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel = update.message.text.strip()
    context.user_data["pending_channel"] = channel
    await update.message.reply_text(
        f"Remove channel {channel}?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm", callback_data="confirm_remove_channel"),
             InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ])
    )
    return ConversationHandler.END

# Confirm button actions
async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = str(query.from_user.id)
    await query.answer()

    if data == "confirm_add_channel":
        channel = context.user_data.get("pending_channel")
        channels = load_channels()
        channels.setdefault(user_id, [])
        if channel not in channels[user_id]:
            channels[user_id].append(channel)
            save_channels(channels)
            await query.edit_message_text(f"✅ Channel {channel} added.")
        else:
            await query.edit_message_text("Channel already exists.")

    elif data == "confirm_remove_channel":
        channel = context.user_data.get("pending_channel")
        channels = load_channels()
        if channel in channels.get(user_id, []):
            channels[user_id].remove(channel)
            save_channels(channels)
            await query.edit_message_text(f"❌ Channel {channel} removed.")
        else:
            await query.edit_message_text("Channel not found.")

    elif data == "confirm_add_admin":
        admin_id = context.user_data.get("pending_admin_id")
        admins = load_admins()
        admins[admin_id] = True
        save_admins(admins)
        await query.edit_message_text(f"✅ User {admin_id} added as admin.")

    elif data == "confirm_remove_admin":
        admin_id = context.user_data.get("pending_admin_id")
        admins = load_admins()
        if admin_id in admins:
            del admins[admin_id]
            save_admins(admins)
            await query.edit_message_text(f"❌ User {admin_id} removed.")
        else:
            await query.edit_message_text("User not found.")

    elif data == "cancel":
        await query.edit_message_text("❌ Operation cancelled.")

# Post to channel
async def post_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    channel = query.data.split("|")[1]
    context.user_data["post_channel"] = channel
    await query.edit_message_text(f"Send the message to post in {channel}:")
    return AWAITING_POST_TEXT

# Forward post message
async def handle_post_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel = context.user_data.get("post_channel")
    if not channel:
        await update.message.reply_text("No channel selected.")
        return ConversationHandler.END
    try:
        await context.bot.copy_message(
            chat_id=channel,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )
        await update.message.reply_text(f"✅ Message posted to {channel}.", reply_markup=get_main_keyboard(update.effective_user.id))
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to post: {e}")
    return ConversationHandler.END

# Cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END

if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu)],
        states={
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
            REMOVE_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin)],
            ADD_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel)],
            REMOVE_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_channel)],
            AWAITING_POST_TEXT: [MessageHandler(filters.ALL, handle_post_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(confirm_callback, pattern="^confirm_"))
    app.add_handler(CallbackQueryHandler(post_callback, pattern="^post_to\|"))
    app.add_handler(CallbackQueryHandler(confirm_callback, pattern="^cancel$"))

    print("Bot is running...")
    app.run_polling()
