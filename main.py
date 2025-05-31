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
from telegram.error import RetryAfter, TelegramError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables. Please set it in .env file.")

OWNER_ID = str(8150652959)  # Convert to string for consistency
ADMINS_FILE = 'admins.json'
CHANNELS_FILE = 'user_channels.json'

# Button text constants
BUTTON_ADD_CHANNEL = "âž• Add Channel"
BUTTON_REMOVE_CHANNEL = "âž– Remove Channel"
BUTTON_MY_CHANNELS = "ðŸ“‹ My Channels"
BUTTON_POST = "ðŸ“¤ Post"
BUTTON_MANAGE_ADMINS = "ðŸ‘¤ Manage Admins"
BUTTON_ADD_ADMIN = "âž• Add Admin"
BUTTON_REMOVE_ADMIN = "âž– Remove Admin"
BUTTON_BACK = "ðŸ”™ Back"

# Ensure data files exist
for file_name in [ADMINS_FILE, CHANNELS_FILE]:
    if not os.path.exists(file_name):
        try:
            with open(file_name, 'w') as f:
                json.dump({}, f)
        except OSError as e:
            print(f"Error creating {file_name}: {e}")
            raise

# File handling with error management
def load_admins():
    try:
        with open(ADMINS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error loading {ADMINS_FILE}: {e}")
        return {}

def save_admins(data):
    try:
        with open(ADMINS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        print(f"Error saving {ADMINS_FILE}: {e}")
        raise

def load_channels():
    try:
        with open(CHANNELS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error loading {CHANNELS_FILE}: {e}")
        return {}

def save_channels(data):
    try:
        with open(CHANNELS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        print(f"Error saving {CHANNELS_FILE}: {e}")
        raise

def is_admin(user_id):
    admins = load_admins()
    return str(user_id) in admins or str(user_id) == OWNER_ID

# States for ConversationHandler
ADD_ADMIN, REMOVE_ADMIN, ADD_CHANNEL, REMOVE_CHANNEL, AWAITING_POST_TEXT = range(5)

# Reply Keyboard for menu
def get_main_keyboard(user_id):
    buttons = [
        [KeyboardButton(BUTTON_ADD_CHANNEL), KeyboardButton(BUTTON_REMOVE_CHANNEL)],
        [KeyboardButton(BUTTON_MY_CHANNELS), KeyboardButton(BUTTON_POST)]
    ]
    if str(user_id) == OWNER_ID:
        buttons.append([KeyboardButton(BUTTON_MANAGE_ADMINS)])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Access denied.")
        return
    await update.message.reply_text("Choose an option:", reply_markup=get_main_keyboard(user_id))

# Main menu handler
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    valid_options = [
        BUTTON_ADD_CHANNEL, BUTTON_REMOVE_CHANNEL, BUTTON_MY_CHANNELS, BUTTON_POST,
        BUTTON_MANAGE_ADMINS, BUTTON_ADD_ADMIN, BUTTON_REMOVE_ADMIN, BUTTON_BACK
    ]

    if text not in valid_options:
        await update.message.reply_text("Please select a valid option from the menu.")
        return ConversationHandler.END

    if text == BUTTON_ADD_CHANNEL:
        await update.message.reply_text("Send the @username of the channel:")
        return ADD_CHANNEL

    elif text == BUTTON_REMOVE_CHANNEL:
        await update.message.reply_text("Send the @username of the channel to remove:")
        return REMOVE_CHANNEL

    elif text == BUTTON_MY_CHANNELS:
        channels = load_channels()
        user_channels = channels.get(str(user_id), [])
        if user_channels:
            await update.message.reply_text("Your channels:
" + "\n".join(user_channels))
        else:
            await update.message.reply_text("You have not added any channels.")
        return ConversationHandler.END

    elif text == BUTTON_POST:
        channels = load_channels()
        user_channels = channels.get(str(user_id), [])
        if not user_channels:
            await update.message.reply_text("You have no channels added.")
            return ConversationHandler.END
        buttons = [[InlineKeyboardButton(name, callback_data=f"post_to|{name}")] for name in user_channels]
        await update.message.reply_text(
            "Select a channel to post in:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return ConversationHandler.END

    elif text == BUTTON_MANAGE_ADMINS and str(user_id) == OWNER_ID:
        buttons = [
            [KeyboardButton(BUTTON_ADD_ADMIN), KeyboardButton(BUTTON_REMOVE_ADMIN)],
            [KeyboardButton(BUTTON_BACK)]
        ]
        await update.message.reply_text(
            "Admin management:",
            reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        )
        return ConversationHandler.END

    elif text == BUTTON_ADD_ADMIN and str(user_id) == OWNER_ID:
        await update.message.reply_text("Send the user ID to add as admin:")
        return ADD_ADMIN

    elif text == BUTTON_REMOVE_ADMIN and str(user_id) == OWNER_ID:
        await update.message.reply_text("Send the user ID to remove from admin:")
        return REMOVE_ADMIN

    elif text == BUTTON_BACK:
        await update.message.reply_text("Main menu:", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

# Admin management
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.text.strip()
    if not user_id.isdigit():
        await update.message.reply_text("Please send a valid numeric user ID.")
        return ConversationHandler.END
    try:
        await context.bot.get_chat(user_id)
    except TelegramError as e:
        await update.message.reply_text(f"Invalid user ID: {e}")
        return ConversationHandler.END
    admins = load_admins()
    admins[user_id] = True
    save_admins(admins)
    await update.message.reply_text(f"âœ… User {user_id} added as admin.")
    return ConversationHandler.END

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.text.strip()
    if not user_id.isdigit():
        await update.message.reply_text("Please send a valid numeric user ID.")
        return ConversationHandler.END
    admins = load_admins()
    if user_id in admins:
        del admins[user_id]
        save_admins(admins)
        await update.message.reply_text(f"âŒ User {user_id} removed from admin.")
    else:
        await update.message.reply_text("User not found in admin list.")
    return ConversationHandler.END

# Channel management
async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel = update.message.text.strip()
    if not channel.startswith('@'):
        await update.message.reply_text("Channel username must start with @.")
        return ConversationHandler.END
    user_id = str(update.effective_user.id)
    try:
        chat = await context.bot.get_chat(channel)
        if chat.type not in ['channel', 'supergroup']:
            await update.message.reply_text("This is not a valid channel.")
            return ConversationHandler.END
        member = await context.bot.get_chat_member(channel, context.bot.id)
        if not member.can_post_messages:
            await update.message.reply_text(f"Bot lacks permission to post in {channel}.")
            return ConversationHandler.END
    except TelegramError as e:
        await update.message.reply_text(f"Error: {e}")
        return ConversationHandler.END
    channels = load_channels()
    channels.setdefault(user_id, [])
    if channel not in channels[user_id]:
        channels[user_id].append(channel)
        save_channels(channels)
        await update.message.reply_text(f"âœ… Channel {channel} added.")
    else:
        await update.message.reply_text("Channel already added.")
    return ConversationHandler.END

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel = update.message.text.strip()
    if not channel.startswith('@'):
        await update.message.reply_text("Channel username must start with @.")
        return ConversationHandler.END
    user_id = str(update.effective_user.id)
    channels = load_channels()
    if channel in channels.get(user_id, []):
        channels[user_id].remove(channel)
        save_channels(channels)
        await update.message.reply_text(f"âŒ Channel {channel} removed.")
    else:
        await update.message.reply_text("Channel not found.")
    return ConversationHandler.END

# Posting
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
        member = await context.bot.get_chat_member(channel, context.bot.id)
        if not member.can_post_messages:
            await update.message.reply_text(f"âŒ Bot lacks permission to post in {channel}.")
            return ConversationHandler.END
        await context.bot.copy_message(
            chat_id=channel,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )
        await update.message.reply_text(f"âœ… Message posted to {channel}.")
    except RetryAfter as e:
        await update.message.reply_text(f"Rate limit hit. Please wait {e.retry_after} seconds.")
    except TelegramError as e:
        await update.message.reply_text(f"âŒ Failed to post: {e}")
    finally:
        context.user_data.pop("post_channel", None)
    return ConversationHandler.END

# Cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("âŒ Operation cancelled.")
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
