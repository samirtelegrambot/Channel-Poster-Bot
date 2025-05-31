import json
import os
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 8150652959  # Replace with your actual Telegram user ID

ADMINS_FILE = 'admins.json'
CHANNELS_FILE = 'user_channels.json'

# Ensure JSON files exist
for file_name in [ADMINS_FILE, CHANNELS_FILE]:
    if not os.path.exists(file_name):
        with open(file_name, 'w') as f:
            json.dump({}, f)


# Helper functions
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
ADD_ADMIN, REMOVE_ADMIN, ADD_CHANNEL, REMOVE_CHANNEL, AWAITING_POST_TEXT, CONFIRM_CANCEL = range(6)


# Main menu keyboard
def get_main_keyboard(user_id):
    buttons = [
        [KeyboardButton("Add Channel"), KeyboardButton("Remove Channel")],
        [KeyboardButton("My Channels"), KeyboardButton("Post")],
    ]
    if user_id == OWNER_ID:
        buttons.append([KeyboardButton("Manage Admins")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


# /start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Access denied.")
        return
    await update.message.reply_text("Choose an option:", reply_markup=get_main_keyboard(user_id))


# Main menu text handler
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "Add Channel":
        await update.message.reply_text("Send the @username of the channel:")
        return ADD_CHANNEL

    elif text == "Remove Channel":
        await update.message.reply_text("Send the @username of the channel to remove:")
        return REMOVE_CHANNEL

    elif text == "My Channels":
        channels = load_channels()
        user_channels = channels.get(str(user_id), [])
        if user_channels:
            # Fixed unterminated string: using "\n" inside the quotes
            await update.message.reply_text("Your channels:\n" + "\n".join(user_channels))
        else:
            await update.message.reply_text("You have not added any channels.")
        return ConversationHandler.END

    elif text == "Post":
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

    elif text == "Manage Admins" and user_id == OWNER_ID:
        buttons = [
            [KeyboardButton("Add Admin"), KeyboardButton("Remove Admin")],
            [KeyboardButton("Back")]
        ]
        await update.message.reply_text(
            "Admin management:",
            reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        )
        return ConversationHandler.END

    elif text == "Add Admin" and user_id == OWNER_ID:
        await update.message.reply_text("Send the user ID to add as admin:")
        return ADD_ADMIN

    elif text == "Remove Admin" and user_id == OWNER_ID:
        await update.message.reply_text("Send the user ID to remove from admin:")
        return REMOVE_ADMIN

    elif text == "Back":
        await update.message.reply_text("Main menu:", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END


# Add admin handler (owner only)
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id_to_add = update.message.text.strip()
    admins = load_admins()
    admins[user_id_to_add] = True
    save_admins(admins)
    await update.message.reply_text(f"User {user_id_to_add} added as admin.")
    return ConversationHandler.END


# Remove admin handler (owner only)
async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id_to_remove = update.message.text.strip()
    admins = load_admins()
    if user_id_to_remove in admins:
        del admins[user_id_to_remove]
        save_admins(admins)
        await update.message.reply_text(f"User {user_id_to_remove} removed from admin.")
    else:
        await update.message.reply_text("User not found in admin list.")
    return ConversationHandler.END


# Add channel: ask for @username, then show Confirm/Cancel buttons
async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['channel_to_add'] = update.message.text.strip()
    buttons = [
        [InlineKeyboardButton("✅ Confirm", callback_data="confirm_add")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    await update.message.reply_text(
        f"Confirm adding {context.user_data['channel_to_add']}?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return CONFIRM_CANCEL


# Remove channel: ask for @username, then show Confirm/Cancel buttons
async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['channel_to_remove'] = update.message.text.strip()
    buttons = [
        [InlineKeyboardButton("✅ Confirm", callback_data="confirm_remove")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    await update.message.reply_text(
        f"Confirm removing {context.user_data['channel_to_remove']}?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return CONFIRM_CANCEL


# Confirmation callback (for both Add and Remove)
async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id_str = str(query.from_user.id)
    channels = load_channels()
    channels.setdefault(user_id_str, [])

    if query.data == "confirm_add":
        channel = context.user_data.get("channel_to_add")
        if channel and channel not in channels[user_id_str]:
            if len(channels[user_id_str]) >= 5:
                await query.edit_message_text("⚠️ You can only add up to 5 channels.")
            else:
                channels[user_id_str].append(channel)
                save_channels(channels)
                await query.edit_message_text(f"✅ Channel {channel} added.")
        else:
            await query.edit_message_text("⚠️ Channel already exists or invalid.")

    elif query.data == "confirm_remove":
        channel = context.user_data.get("channel_to_remove")
        if channel and channel in channels[user_id_str]:
            channels[user_id_str].remove(channel)
            save_channels(channels)
            await query.edit_message_text(f"❌ Channel {channel} removed.")
        else:
            await query.edit_message_text("⚠️ Channel not found.")

    elif query.data == "cancel":
        await query.edit_message_text("Operation cancelled.")

    return ConversationHandler.END


# When the user taps one of the InlineKeyboardButtons under “Post”
async def post_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    channel = query.data.split("|")[1]
    context.user_data["post_channel"] = channel
    await query.edit_message_text(f"Send the message to post in {channel}:")
    return AWAITING_POST_TEXT


# After the user has selected a channel and is now sending whatever they want posted
async def handle_post_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel = context.user_data.get("post_channel")
    if not channel:
        await update.message.reply_text("No channel selected.")
        return ConversationHandler.END

    try:
        # copy whatever the user sent (text/photo/sticker/video/etc.) into the target channel
        await context.bot.copy_message(
            chat_id=channel,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )
        await update.message.reply_text(f"✅ Message posted to {channel}.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to post: {e}")

    return ConversationHandler.END


# /cancel fallback
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled.")
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
            CONFIRM_CANCEL: [CallbackQueryHandler(confirm_callback, pattern="^(confirm_add|confirm_remove|cancel)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(post_callback, pattern="^post_to\\|"))

    print("Bot is running...")
    app.run_polling()
