from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from mizuki.admin import admin_only
from util import load_banned_words, load_channels, load_remove_words, load_replace_words, TARGET_FILE, EMOJI_FILE, SYMBOL_FILE
import json
import math
import os

ITEMS_PER_PAGE = 10

async def create_pagination_buttons(current_page: int, total_pages: int, prefix: str):

    buttons = []
    
    if current_page > 0:
        buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"{prefix}:{current_page-1}"))
    
    buttons.append(InlineKeyboardButton(f"{current_page+1}/{total_pages}", callback_data=" "))
    
    if current_page < total_pages - 1:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"{prefix}:{current_page+1}"))
    
    return InlineKeyboardMarkup([buttons])

def load_emoji_replacements():

    if not os.path.exists(EMOJI_FILE):
        return {}
    try:
        with open(EMOJI_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading emoji replacements: {e}")
        return {}

def load_preserve_symbols():

    try:
        if not os.path.exists(SYMBOL_FILE):
            return []
        with open(SYMBOL_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

@admin_only
async def list_banned(update: Update, context: ContextTypes.DEFAULT_TYPE):

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

@admin_only
async def list_emoji_replacements(update: Update, context: ContextTypes.DEFAULT_TYPE):

    emoji_replacements = load_emoji_replacements()
    total_pages = math.ceil(len(emoji_replacements) / ITEMS_PER_PAGE)
    current_page = 0
    
    if not emoji_replacements:
        await update.message.reply_text("No emoji replacements found.")
        return
    
    start_idx = current_page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_items = list(emoji_replacements.items())[start_idx:end_idx]
    
    message = "😀 <b>Emoji Replacements</b>:\n\n" + "\n".join(f"• {k} → {v}" for k, v in page_items)
    
    keyboard = await create_pagination_buttons(current_page, total_pages, "lre")
    await update.message.reply_text(message, reply_markup=keyboard, parse_mode="HTML")

@admin_only
async def list_preserve_symbols(update: Update, context: ContextTypes.DEFAULT_TYPE):

    symbols = load_preserve_symbols()
    total_pages = math.ceil(len(symbols) / ITEMS_PER_PAGE)
    current_page = 0
    
    if not symbols:
        await update.message.reply_text("No preserved symbols found.")
        return
    
    start_idx = current_page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_symbols = symbols[start_idx:end_idx]
    
    message = "🔣 <b>Preserved Symbols</b>:\n\n" + "\n".join(f"• {symbol}" for symbol in page_symbols)
    
    keyboard = await create_pagination_buttons(current_page, total_pages, "lsy")
    await update.message.reply_text(message, reply_markup=keyboard, parse_mode="HTML")

async def handle_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

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
    elif prefix == "lre":
        items = list(load_emoji_replacements().items())
        title = "😀 <b>Emoji Replacements</b>:\n\n"
        item_format = "• {} → {}"
    elif prefix == "lsy":
        items = load_preserve_symbols()
        title = "🔣 <b>Preserved Symbols</b>:\n\n"
        item_format = "• {}"
    else:
        return
    
    total_pages = math.ceil(len(items) / ITEMS_PER_PAGE)
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    
    if prefix in ["lrp", "lre"]:
        page_items = items[start_idx:end_idx]
        message = title + "\n".join(item_format.format(k, v) for k, v in page_items)
    else:
        page_items = items[start_idx:end_idx]
        message = title + "\n".join(item_format.format(item) for item in page_items)
    
    keyboard = await create_pagination_buttons(page, total_pages, prefix)
    await query.edit_message_text(message, reply_markup=keyboard, parse_mode="HTML")

@admin_only
async def list_forward_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all forward groups with their links"""
    try:
        with open(TARGET_FILE, 'r') as f:
            forward_groups = json.load(f)
        
        if not forward_groups:
            await update.message.reply_text("No forward groups found.")
            return
        
        message = "📢 <b>Forward Groups</b>:\n\n"
        for group_id in forward_groups:
            try:
                chat = await context.bot.get_chat(group_id)
                message += f"• {chat.title} (ID: {group_id})\n"
                message += f"   Link: {chat.invite_link or 'No link available'}\n\n"
            except Exception as e:
                message += f"• ID: {group_id} (Error fetching info: {str(e)})\n\n"
        
        await update.message.reply_text(message, parse_mode="HTML")
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

def get_list_handlers():
    """Return all list command handlers"""
    return [
        CommandHandler("lb", list_banned),
        CommandHandler("lc", list_channels),
        CommandHandler("lrm", list_remove),
        CommandHandler("lrp", list_replace),
        CommandHandler("lre", list_emoji_replacements),
        CommandHandler("lsy", list_preserve_symbols),
        CommandHandler("lf", list_forward_groups),
        CallbackQueryHandler(handle_list_callback, pattern=r"^(lb|lrm|lrp|lc|lre|lsy):[0-9]+$")
    ]