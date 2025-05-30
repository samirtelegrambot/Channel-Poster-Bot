import json
import os
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters
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


# States
ADD_ADMIN, REMOVE_ADMIN, ADD_CHANNEL, REMOVE_CHANNEL, AWAITING_POST_TEXT = range(5)


def get_main_keyboard(user_id):
    buttons = [
        [KeyboardButton("➕ Add Channel"), KeyboardButton("➖ Remove Channel")],
        [KeyboardButton("📋 My Channels"), KeyboardButton("📤 Post")]
    ]
    if user_id == OWNER_ID:
        buttons.append([KeyboardButton("👤 Manage Admins")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Access denied.")
        return
    await update.message.reply_text("Choose an option:", reply_markup=get_main_keyboard(user_id))


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "➕ Add Channel":
        await update.message.reply_text("Send the @username of the channel:")
        return ADD_CHANNEL

    elif text == "➖ Remove Channel":
        await update.message.reply_text("Send the @username of the channel to remove:")
        return REMOVE_CHANNEL

    elif text == "📋 My Channels":
        channels = load_channels()
        user_channels = channels.get(str(user_id), [])
        if user_channels:
            await update.message.reply_text("Your channels:\n" + "\n".join(user_channels))
        else:
            await update.message.reply_text("You have not added any channels.")
        return ConversationHandler.END

    elif text == "📤 Post":
        channels = load_channels()
        user_channels = channels.get(str(user_id), [])
        if not user_channels:
            await update.message.reply_text("You have no channels added.")
            return ConversationHandler.END

        buttons = [
            [InlineKeyboardButton(name, callback_data=f"post_to|{name}")]
            for name in user_channels
        ]
        await update.message.reply_text(
            "Select a channel to post in:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return ConversationHandler.END

    elif text == "👤 Manage Admins" and user_id == OWNER_ID:
        buttons = [
            [KeyboardButton("➕ Add Admin"), KeyboardButton("➖ Remove Admin")],
            [KeyboardButton("🔙 Back")]
        ]
        await update.message.reply_text(
            "Admin management:",
            reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        )
        return ConversationHandler.END

    elif text == "➕ Add Admin" and user_id == OWNER_ID:
        await update.message.reply_text("Send the user ID to add as admin:")
        return ADD_ADMIN

    elif text == "➖ Remove Admin" and user_id == OWNER_ID:
        await update.message.reply_text("Send the user ID to remove from admin:")
        return REMOVE_ADMIN

    elif text == "🔙 Back":
        await update.message.reply_text("Main menu:", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END


async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.text.strip()
    admins = load_admins()
    admins[user_id] = True
    save_admins(admins)
    await update.message.reply_text(f"✅ User {user_id} added as admin.")
    return ConversationHandler.END


async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.text.strip()
    admins = load_admins()
    if user_id in admins:
        del admins[user_id]
        save_admins(admins)
        await update.message.reply_text(f"❌ User {user_id} removed from admin.")
    else:
        await update.message.reply_text("User not found in admin list.")
    return ConversationHandler.END


async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel = update.message.text.strip()
    user_id = str(update.effective_user.id)
    channels = load_channels()
    channels.setdefault(user_id, [])
    if channel not in channels[user_id]:
        channels[user_id].append(channel)
        save_channels(channels)
        await update.message.reply_text(f"✅ Channel {channel} added.")
    else:
        await update.message.reply_text("Channel already added.")
    return ConversationHandler.END


async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel = update.message.text.strip()
    user_id = str(update.effective_user.id)
    channels = load_channels()
    if channel in channels.get(user_id, []):
        channels[user_id].remove(channel)
        save_channels(channels)
        await update.message.reply_text(f"❌ Channel {channel} removed.")
    else:
        await update.message.reply_text("Channel not found.")
    return ConversationHandler.END


async def post_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    channel = query.data.split("|")[1]
    context.user_data["post_channel"] = channel
    await query.edit_message_text(f"Send the message to post in {channel}:")
    return AWAITING_POST_TEXT


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
        await update.message.reply_text(f"✅ Message posted to {channel}.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to post: {e}")
    return ConversationHandler.END


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
    app.add_handler(CallbackQueryHandler(post_callback, pattern="^post_to\|"))

    print("Bot is running...")
    app.run_polling()
