
import json
import os
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from util import EMOJI_FILE

def load_emoji_replacements():
    """Load emoji replacements from JSON file"""
    if not os.path.exists(EMOJI_FILE):
        return {}
    try:
        with open(EMOJI_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading emoji replacements: {e}")
        return {}

def save_emoji_replacements(data):
    """Save emoji replacements to JSON file"""
    try:
        with open(EMOJI_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving emoji replacements: {e}")
        return False

async def add_emoji_replacement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add new emoji replacement (/arep_em command)"""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /arep_em <emoji> <replacement>")
        return

    emoji = context.args[0]
    replacement = ' '.join(context.args[1:])
    
    replacements = load_emoji_replacements()
    replacements[emoji] = replacement
    
    if save_emoji_replacements(replacements):
        await update.message.reply_text(f"✅ Replaced: {emoji} → {replacement}")
    else:
        await update.message.reply_text("❌ Failed to save replacement")

async def remove_emoji_replacement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove emoji replacement (/rrep_em command)"""
    if not context.args:
        await update.message.reply_text("Usage: /rrep_em <emoji>")
        return

    emoji = context.args[0]
    replacements = load_emoji_replacements()
    
    if emoji in replacements:
        del replacements[emoji]
        if save_emoji_replacements(replacements):
            await update.message.reply_text(f"✅ Removed: {emoji}")
        else:
            await update.message.reply_text("❌ Failed to save changes")
    else:
        await update.message.reply_text(f"❌ {emoji} not found in replacements")

def get_handlers():
    return [
        CommandHandler("arep_em", add_emoji_replacement),
        CommandHandler("rrep_em", remove_emoji_replacement)
    ]