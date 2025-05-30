import json
import os
from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler,
    filters, ConversationHandler
)
from dotenv import load_dotenv

load_dotenv()

# Load environment token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Owner ID
OWNER_ID = 8150652959  # Replace with your actual ID

# File paths
ADMINS_FILE = 'admins.json'
CHANNELS_FILE = 'user_channels.json'

# Ensure data files exist
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

def is_admin(user_id):
    admins = load_admins()
    return str(user_id) in admins or user_id == OWNER_ID

# Conversation states
ADD_ADMIN, REMOVE_ADMIN = range(2)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("Access denied.")
        return

    # Reply keyboard buttons
    buttons = [
        [KeyboardButton("➕ Add Channel"), KeyboardButton("➖ Remove Channel")],
        [KeyboardButton("📋 My Channels"), KeyboardButton("📤 Post")]
    ]

    if user_id == OWNER_ID:
        buttons.append([KeyboardButton("👤 Manage Admins")])

    await update.message.reply_text(
        "Choose an option:",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )

# Manage Admins
async def manage_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Choose:\n➕ Send 'Add Admin'\n➖ Send 'Remove Admin'\n❌ Or send /cancel to cancel"
    )

async def ask_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send the user ID to add as admin:")
    return ADD_ADMIN

async def ask_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send the user ID to remove from admin:")
    return REMOVE_ADMIN

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

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END

# Main function
if __name__ == '__main__':
    app = Application.builder().token(BOT_TOKEN).build()

    # Command handler
    app.add_handler(CommandHandler("start", start))

    # Conversation for add/remove admin
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & filters.Regex("^Add Admin$"), ask_add_admin),
            MessageHandler(filters.TEXT & filters.Regex("^Remove Admin$"), ask_remove_admin)
        ],
        states={
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
            REMOVE_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv_handler)

    # Text-based trigger for manage admin menu
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^👤 Manage Admins$"), manage_admins))

    print("Bot is running...")
    app.run_polling()
