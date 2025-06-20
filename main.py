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

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

# Fixed channel IDs
FIXED_CHANNELS = [
    -1002504723776,  # Channel 1
    -1002489624380   # Channel 2
]

# Create bot application
app = Application.builder().token(TOKEN).build()

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("🚫 You are not authorized to use this bot.")
        return
    
    # Initialize user data if not exists
    if 'forwarded_messages' not in context.user_data:
        context.user_data['forwarded_messages'] = []
    if 'selected_channels' not in context.user_data:
        context.user_data['selected_channels'] = []
    
    await update.message.reply_text(
        "✅ Welcome!\n"
        "Forward messages to me.\n"
        "Then use the buttons to select channels and post."
    )

# Handle forwarded messages
async def handle_forwarded(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("🚫 You are not authorized to use this bot.")
        return

    # Initialize storage if not exists
    if 'forwarded_messages' not in context.user_data:
        context.user_data['forwarded_messages'] = []
    
    # Store message reference
    context.user_data['forwarded_messages'].append(update.message)

    await update.message.reply_text(
        "📥 Message saved.\n"
        "Click below to select channels and post:",
        reply_markup=channel_selection_keyboard()
    )

# Inline keyboard for channel selection
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
    # Verify user is owner
    if update.effective_user.id != OWNER_ID:
        await update.callback_query.answer("Not authorized")
        return

    query = update.callback_query
    await query.answer()

    # Get current state from user data
    selected_channels = context.user_data.get('selected_channels', [])

    if query.data.startswith("toggle_"):
        channel_id = int(query.data.split("_")[1])
        if channel_id in selected_channels:
            selected_channels.remove(channel_id)
        else:
            selected_channels.append(channel_id)
        
        context.user_data['selected_channels'] = selected_channels
        status = "\n".join([f"✅ Channel {FIXED_CHANNELS.index(cid)+1}" 
                          for cid in selected_channels]) or "None"
        await query.edit_message_text(
            f"🔘 Selected channels:\n{status}",
            reply_markup=channel_selection_keyboard()
        )

    elif query.data == "select_all":
        context.user_data['selected_channels'] = FIXED_CHANNELS.copy()
        await query.edit_message_text(
            "✅ All channels selected.",
            reply_markup=channel_selection_keyboard()
        )

    elif query.data == "unselect_all":
        context.user_data['selected_channels'] = []
        await query.edit_message_text(
            "❌ All channels unselected.",
            reply_markup=channel_selection_keyboard()
        )

    elif query.data == "post_now":
        forwarded_messages = context.user_data.get('forwarded_messages', [])
        selected_channels = context.user_data.get('selected_channels', [])

        if not selected_channels:
            await query.edit_message_text(
                "⚠️ Please select at least one channel.",
                reply_markup=channel_selection_keyboard()
            )
            return

        if not forwarded_messages:
            await query.edit_message_text(
                "⚠️ No messages to post.",
                reply_markup=channel_selection_keyboard()
            )
            return

        # Post messages and collect errors
        errors = []
        for msg in forwarded_messages:
            for channel_id in selected_channels:
                try:
                    await msg.copy(chat_id=channel_id)
                except Exception as e:
                    errors.append(f"Failed to post to {channel_id}: {str(e)}")

        # Clear stored data
        context.user_data['forwarded_messages'] = []
        context.user_data['selected_channels'] = []

        # Handle errors
        if errors:
            error_text = "❌ Some messages failed to post:\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                error_text += f"\n... and {len(errors)-5} more errors."
            await query.edit_message_text(error_text)
        else:
            await query.edit_message_text("✅ All messages posted successfully!")

# Register handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_forwarded))
app.add_handler(CallbackQueryHandler(handle_callback))

print("🚀 Bot is running...")
app.run_polling()
