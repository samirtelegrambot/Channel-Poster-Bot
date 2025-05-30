import logging from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes import sqlite3 from config import TOKEN, SUPER_ADMIN_ID from db import init_db, add_user, remove_user, is_admin, get_user_channels, add_channel, remove_channel

logging.basicConfig(level=logging.INFO) logger = logging.getLogger(name)

Initialize the database

init_db()

--- BUTTON KEYBOARDS ---

def admin_keyboard(): keyboard = [ [InlineKeyboardButton("➕ Add Channel", callback_data='add_channel')], [InlineKeyboardButton("🗑️ Remove Channel", callback_data='remove_channel')], [InlineKeyboardButton("📋 My Channels", callback_data='my_channels')], [InlineKeyboardButton("📤 Post to Channel", callback_data='post')] ] return InlineKeyboardMarkup(keyboard)

--- COMMAND HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = update.effective_user.id if is_admin(user_id): await update.message.reply_text("👋 Welcome Admin! Choose an option:", reply_markup=admin_keyboard()) else: await update.message.reply_text("❌ You are not authorized to use this bot.")

async def add_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): if update.effective_user.id != SUPER_ADMIN_ID: await update.message.reply_text("❌ Only super admin can add users.") return if not context.args: await update.message.reply_text("Usage: /add_user <user_id>") return user_id = int(context.args[0]) add_user(user_id) await update.message.reply_text(f"✅ User {user_id} added as admin.")

async def remove_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): if update.effective_user.id != SUPER_ADMIN_ID: await update.message.reply_text("❌ Only super admin can remove users.") return if not context.args: await update.message.reply_text("Usage: /remove_user <user_id>") return user_id = int(context.args[0]) remove_user(user_id) await update.message.reply_text(f"✅ User {user_id} removed.")

--- CALLBACK HANDLER ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE): query = update.callback_query user_id = query.from_user.id await query.answer() if not is_admin(user_id): await query.edit_message_text("❌ Unauthorized") return

if query.data == "add_channel":
    context.user_data['action'] = 'adding_channel'
    await query.edit_message_text("🔹 Send me the @username of the channel to add:")

elif query.data == "remove_channel":
    context.user_data['action'] = 'removing_channel'
    await query.edit_message_text("🗑️ Send me the @username of the channel to remove:")

elif query.data == "my_channels":
    channels = get_user_channels(user_id)
    if not channels:
        await query.edit_message_text("📭 You have no channels added.")
    else:
        text = "📋 Your Channels:\n" + "\n".join(f"- {ch}" for ch in channels)
        await query.edit_message_text(text)

elif query.data == "post":
    context.user_data['action'] = 'posting'
    await query.edit_message_text("📨 Send me the message to post:")

--- MESSAGE HANDLER ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = update.effective_user.id if not is_admin(user_id): return action = context.user_data.get('action') if action == 'adding_channel': add_channel(user_id, update.message.text.strip()) await update.message.reply_text("✅ Channel added.", reply_markup=admin_keyboard()) elif action == 'removing_channel': remove_channel(user_id, update.message.text.strip()) await update.message.reply_text("🗑️ Channel removed.", reply_markup=admin_keyboard()) elif action == 'posting': channels = get_user_channels(user_id) for ch in channels: try: await context.bot.send_message(chat_id=ch, text=update.message.text) except Exception as e: logger.error(f"Failed to post to {ch}: {e}") await update.message.reply_text("✅ Message posted.", reply_markup=admin_keyboard()) context.user_data['action'] = None

--- MAIN FUNCTION ---

def main(): app = Application.builder().token(TOKEN).build() app.add_handler(CommandHandler("start", start)) app.add_handler(CommandHandler("add_user", add_user_cmd)) app.add_handler(CommandHandler("remove_user", remove_user_cmd)) app.add_handler(CallbackQueryHandler(button_handler)) app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)) app.run_polling()

if name == 'main': main()

