import json
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, filters, ConversationHandler
)

# Load environment token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Set your Telegram user ID as owner
OWNER_ID = 8150652959

ADMINS_FILE = 'admins.json'
CHANNELS_FILE = 'user_channels.json'

# Ensure files exist
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

def is_admin(user_id):
    admins = load_admins()
    return str(user_id) in admins or user_id == OWNER_ID

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    print(f"[DEBUG] user_id: {user_id}, OWNER_ID: {OWNER_ID}")

    if not is_admin(user_id):
        await update.message.reply_text("Access denied.")
        return

    buttons = [
        [InlineKeyboardButton("➕ Add Channel", callback_data="add_channel")],
        [InlineKeyboardButton("➖ Remove Channel", callback_data="remove_channel")],
        [InlineKeyboardButton("📋 My Channels", callback_data="my_channels")],
        [InlineKeyboardButton("📤 Post", callback_data="post")]
    ]

    if user_id == OWNER_ID:
        print("[DEBUG] Owner matched — showing Manage Admins button.")
        buttons.append([InlineKeyboardButton("👤 Manage Admins", callback_data="manage_admins")])

    await update.message.reply_text("Choose an option:", reply_markup=InlineKeyboardMarkup(buttons))

# Admin management
ADD_ADMIN, REMOVE_ADMIN = range(2)

async def manage_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    buttons = [
        [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
        [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")]
    ]
    await query.edit_message_text("Manage admins:", reply_markup=InlineKeyboardMarkup(buttons))

async def ask_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Send the user ID to add as admin:")
    return ADD_ADMIN

async def ask_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Send the user ID to remove from admin:")
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
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

# Main application entry
if __name__ == '__main__':
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_add_admin, pattern="^add_admin$"),
            CallbackQueryHandler(ask_remove_admin, pattern="^remove_admin$")
        ],
        states={
            ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
            REMOVE_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(manage_admins, pattern="^manage_admins$"))

    print("Bot is running...")
    app.run_polling()
