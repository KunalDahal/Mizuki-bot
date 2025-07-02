# list.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from commands.admin import admin_only
from util import load_banned_words, load_channels, load_remove_words, load_replace_words
import math

ITEMS_PER_PAGE = 10

async def create_pagination_buttons(current_page: int, total_pages: int, prefix: str):
    """Create pagination buttons"""
    buttons = []
    
    if current_page > 0:
        buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"{prefix}:{current_page-1}"))
    
    buttons.append(InlineKeyboardButton(f"{current_page+1}/{total_pages}", callback_data=" "))
    
    if current_page < total_pages - 1:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"{prefix}:{current_page+1}"))
    
    return InlineKeyboardMarkup([buttons])

@admin_only
async def list_banned(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List banned words with pagination"""
    banned_words = load_banned_words()
    total_pages = math.ceil(len(banned_words) / ITEMS_PER_PAGE)
    current_page = 0
    
    if not banned_words:
        await update.message.reply_text("No banned words found.")
        return
    
    start_idx = current_page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_words = banned_words[start_idx:end_idx]
    
    message = "📛 <b>Banned Words</b>:\n\n" + "\n".join(f"• {word}" for word in page_words)
    
    keyboard = await create_pagination_buttons(current_page, total_pages, "lb")
    await update.message.reply_text(message, reply_markup=keyboard, parse_mode="HTML")

@admin_only
async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List monitored channels with pagination"""
    channels = load_channels()
    total_pages = math.ceil(len(channels) / ITEMS_PER_PAGE)
    current_page = 0
    
    if not channels:
        await update.message.reply_text("No monitored channels found.")
        return
    
    start_idx = current_page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_channels = channels[start_idx:end_idx]
    
    message = "📢 <b>Monitored Channels</b>:\n\n" + "\n".join(f"• {channel}" for channel in page_channels)
    
    keyboard = await create_pagination_buttons(current_page, total_pages, "lc")
    await update.message.reply_text(message, reply_markup=keyboard, parse_mode="HTML")

@admin_only
async def list_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List remove words with pagination"""
    remove_words = load_remove_words()
    total_pages = math.ceil(len(remove_words) / ITEMS_PER_PAGE)
    current_page = 0
    
    if not remove_words:
        await update.message.reply_text("No remove words found.")
        return
    
    start_idx = current_page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_words = remove_words[start_idx:end_idx]
    
    message = "🗑️ <b>Remove Words</b>:\n\n" + "\n".join(f"• {word}" for word in page_words)
    
    keyboard = await create_pagination_buttons(current_page, total_pages, "lrm")
    await update.message.reply_text(message, reply_markup=keyboard, parse_mode="HTML")

@admin_only
async def list_replace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List replace words with pagination"""
    replace_words = load_replace_words()
    total_pages = math.ceil(len(replace_words) / ITEMS_PER_PAGE)
    current_page = 0
    
    if not replace_words:
        await update.message.reply_text("No replace words found.")
        return
    
    start_idx = current_page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_words = list(replace_words.items())[start_idx:end_idx]
    
    message = "🔁 <b>Replace Words</b>:\n\n" + "\n".join(f"• {k} → {v}" for k, v in page_words)
    
    keyboard = await create_pagination_buttons(current_page, total_pages, "lrp")
    await update.message.reply_text(message, reply_markup=keyboard, parse_mode="HTML")

async def handle_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pagination callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    prefix = data[0]
    page = int(data[1])
    
    if prefix == "lb":
        items = load_banned_words()
        title = "📛 <b>Banned Words</b>:\n\n"
        item_format = "• {}"
    elif prefix == "lc":
        items = load_channels()
        title = "📢 <b>Monitored Channels</b>:\n\n"
        item_format = "• {}"
    elif prefix == "lrm":
        items = load_remove_words()
        title = "🗑️ <b>Remove Words</b>:\n\n"
        item_format = "• {}"
    elif prefix == "lrp":
        items = list(load_replace_words().items())
        title = "🔁 <b>Replace Words</b>:\n\n"
        item_format = "• {} → {}"
    else:
        return
    
    total_pages = math.ceil(len(items) / ITEMS_PER_PAGE)
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    
    if prefix == "lrp":
        page_items = items[start_idx:end_idx]
        message = title + "\n".join(item_format.format(k, v) for k, v in page_items)
    else:
        page_items = items[start_idx:end_idx]
        message = title + "\n".join(item_format.format(item) for item in page_items)
    
    keyboard = await create_pagination_buttons(page, total_pages, prefix)
    await query.edit_message_text(message, reply_markup=keyboard, parse_mode="HTML")

def get_list_handlers():
    """Return all list command handlers"""
    return [
        CommandHandler("lb", list_banned),
        CommandHandler("lc", list_channels),
        CommandHandler("lrm", list_remove),
        CommandHandler("lrp", list_replace),
        CallbackQueryHandler(handle_list_callback, pattern=r"^(lb|lrm|lrp|lc):[0-9]+$")
    ]