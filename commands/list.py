from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from commands.admin import admin_only
from util import load_channels, load_remove_words, load_replace_words
from telethon.errors import ChannelPrivateError, ChannelInvalidError
from telethon.tl.types import Channel
import logging

logger = logging.getLogger(__name__)

# Constants for pagination
ITEMS_PER_PAGE = 10

async def send_list_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the main list menu with buttons"""
    keyboard = [
        [InlineKeyboardButton("📊 Channels", callback_data="list:channels:0")],
        [InlineKeyboardButton("🗑️ Remove Words", callback_data="list:remove:0")],
        [InlineKeyboardButton("🔄 Replace Words", callback_data="list:replace:0")],
        [InlineKeyboardButton("❌ Close", callback_data="list:close")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text="📋 Choose a list to view:",
            reply_markup=reply_markup
        )
    else:
        message = await update.message.reply_text(
            "📋 Choose a list to view:",
            reply_markup=reply_markup
        )
        # Store message ID for possible deletion later
        context.user_data['list_message_id'] = message.message_id

@admin_only
async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main list command handler"""
    await send_list_menu(update, context)

async def show_channels_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    """Show a page of channel list"""
    channel_ids = load_channels()
    if not channel_ids:
        await update.callback_query.edit_message_text("ℹ️ No channels are being monitored")
        return
    
    # Pagination
    total_pages = (len(channel_ids) // ITEMS_PER_PAGE + (1 if len(channel_ids) % ITEMS_PER_PAGE != 0 else 0))
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(channel_ids))
    
    message = f"📊 Monitored Channels (Page {page+1}/{total_pages}):\n\n"
    
    # Get Telethon client
    monitor = context.bot_data.get('monitor')
    if not monitor or not hasattr(monitor, 'client'):
        await update.callback_query.edit_message_text("❌ Monitor not initialized")
        return
        
    client = monitor.client
    
    for i in range(start_idx, end_idx):
        channel_id = channel_ids[i]
        try:
            entity = await client.get_entity(channel_id)
            if isinstance(entity, Channel):
                username = f"@{entity.username}" if entity.username else "No username"
                title = entity.title or "No title"
                message += f"🔹 {i+1}. {title}\n   👤 {username}\n   🆔 {channel_id}\n\n"
            else:
                message += f"🔹 {i+1}. ID: {channel_id}\n   ❌ Not a channel/group\n\n"
        except ChannelPrivateError:
            message += f"🔹 {i+1}. ID: {channel_id}\n   🔒 Private channel (no access)\n\n"
        except ChannelInvalidError:
            message += f"🔹 {i+1}. ID: {channel_id}\n   ❌ Invalid channel ID\n\n"
        except Exception as e:
            message += f"🔹 {i+1}. ID: {channel_id}\n   ⚠️ Error: {str(e)}\n\n"
            logger.error(f"Error fetching channel {channel_id}: {e}")
    
    # Create pagination buttons
    keyboard = []
    if page > 0:
        keyboard.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"list:channels:{page-1}"))
    if end_idx < len(channel_ids):
        keyboard.append(InlineKeyboardButton("Next ➡️", callback_data=f"list:channels:{page+1}"))
    
    keyboard.append(InlineKeyboardButton("🔙 Back", callback_data="list:menu"))
    
    reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
    
    await update.callback_query.edit_message_text(
        text=message,
        reply_markup=reply_markup
    )

async def show_remove_words_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    """Show a page of remove words list"""
    words = load_remove_words()
    if not words:
        await update.callback_query.edit_message_text("ℹ️ No words in removal list")
        return
    
    # Pagination
    total_pages = (len(words) // ITEMS_PER_PAGE + (1 if len(words) % ITEMS_PER_PAGE != 0 else 0))
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(words))
    
    message = f"🗑️ Removal List (Page {page+1}/{total_pages}):\n\n"
    
    for i in range(start_idx, end_idx):
        message += f"{i+1}. {words[i]}\n"
    
    # Create pagination buttons
    keyboard = []
    if page > 0:
        keyboard.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"list:remove:{page-1}"))
    if end_idx < len(words):
        keyboard.append(InlineKeyboardButton("Next ➡️", callback_data=f"list:remove:{page+1}"))
    
    keyboard.append(InlineKeyboardButton("🔙 Back", callback_data="list:menu"))
    
    reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
    
    await update.callback_query.edit_message_text(
        text=message,
        reply_markup=reply_markup
    )

async def show_replace_words_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    """Show a page of replace words list"""
    replace_words = load_replace_words()
    if not replace_words:
        await update.callback_query.edit_message_text("ℹ️ No word replacements configured")
        return
    
    # Convert to list for pagination
    replacements = list(replace_words.items())
    
    # Pagination
    total_pages = (len(replacements) // ITEMS_PER_PAGE + (1 if len(replacements) % ITEMS_PER_PAGE != 0 else 0))
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(replacements))
    
    message = f"🔄 Word Replacements (Page {page+1}/{total_pages}):\n\n"
    
    for i in range(start_idx, end_idx):
        original, replacement = replacements[i]
        message += f"{i+1}. {original} → {replacement}\n"
    
    # Create pagination buttons
    keyboard = []
    if page > 0:
        keyboard.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"list:replace:{page-1}"))
    if end_idx < len(replacements):
        keyboard.append(InlineKeyboardButton("Next ➡️", callback_data=f"list:replace:{page+1}"))
    
    keyboard.append(InlineKeyboardButton("🔙 Back", callback_data="list:menu"))
    
    reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
    
    await update.callback_query.edit_message_text(
        text=message,
        reply_markup=reply_markup
    )

async def handle_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from list buttons"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    action = data[1]
    
    if action == "close":
        # Delete the list message
        try:
            await query.delete_message()
        except:
            # If message is too old to delete, just edit it
            await query.edit_message_text("✅ List closed")
        return
    
    if action == "menu":
        await send_list_menu(update, context)
        return
        
    page = int(data[2]) if len(data) > 2 else 0
    
    if action == "channels":
        await show_channels_page(update, context, page)
    elif action == "remove":
        await show_remove_words_page(update, context, page)
    elif action == "replace":
        await show_replace_words_page(update, context, page)

def get_list_channels_handler():
    return [
        CommandHandler("list", list_command),
        CallbackQueryHandler(handle_list_callback, pattern="^list:")
    ]