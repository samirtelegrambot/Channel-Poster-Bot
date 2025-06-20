import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Load environment variables from .env file
load_dotenv()
TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

# Define your fixed channel IDs (replace with your actual ones)
FIXED_CHANNELS = [
    -1002504723776,  # Channel 1
    -1002489624380   # Channel 2
]
# Temporary storage for forwarded messages and selected channels
forwarded_messages = []
selected_channels = []

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("🚫 You are not authorized to use this bot.")
        return
    await update.message.reply_text(
        "✅ Welcome! Forward messages to me.\n"
        "When ready, use the buttons to select channels and post."
    )

# Handle any forwarded message
async def handle_forwarded(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("🚫 You are not authorized to use this bot.")
        return

    # Save the forwarded message
    forwarded_messages.append(update.message)

    await update.message.reply_text(
        "📥 Message saved.\n"
        "Click below to select channels and post:",
        reply_markup=channel_selection_keyboard()
    )

# Generate inline keyboard for channel selection and actions
def channel_selection_keyboard():
    buttons = [
        [InlineKeyboardButton(f"Channel {idx+1}", callback_data=f"toggle_{channel_id}")]
        for idx, channel_id in enumerate(FIXED_CHANNELS)
    ]
    buttons.append([
        InlineKeyboardButton("✅ Select All", callback_data="select_all"),
        InlineKeyboardButton("❌ Unselect All", callback_data="unselect_all"),
    ])
    buttons.append([
        InlineKeyboardButton("🚀 POST", callback_data="post_now"),
    ])
    return InlineKeyboardMarkup(buttons)

# Handle inline button actions
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global selected_channels
    query = update.callback_query
    await query.answer()

    if query.data.startswith("toggle_"):
        channel_id = int(query.data.split("_")[1])
        if channel_id in selected_channels:
            selected_channels.remove(channel_id)
        else:
            selected_channels.append(channel_id)
        await query.edit_message_text(
            "🔘 Select channels:",
            reply_markup=channel_selection_keyboard()
        )

    elif query.data == "select_all":
        selected_channels = FIXED_CHANNELS.copy()
        await query.edit_message_text(
            "✅ All channels selected.",
            reply_markup=channel_selection_keyboard()
        )

    elif query.data == "unselect_all":
        selected_channels = []
        await query.edit_message_text(
            "❌ All channels unselected.",
            reply_markup=channel_selection_keyboard()
        )

    elif query.data == "post_now":
        if not selected_channels:
            await query.edit_message_text(
                "⚠️ Please select at least one channel.",
                reply_markup=channel_selection_keyboard()
            )
            return

        for msg in forwarded_messages:
            for channel_id in selected_channels:
                try:
                    await msg.copy(chat_id=channel_id)
                except Exception as e:
                    print(f"❌ Failed to post to {channel_id}: {e}")

        # Clear storage after posting
        forwarded_messages.clear()
        selected_channels.clear()

        await query.edit_message_text("✅ All messages posted successfully!")

# Initialize bot application
app = Application.builder().token(TOKEN).build()

# Register handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_forwarded))
app.add_handler(CallbackQueryHandler(handle_callback))

# Start polling
print("🚀 Bot is running with polling...")
app.run_polling()
