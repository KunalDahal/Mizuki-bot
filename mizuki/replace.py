from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from util import load_replace_words, save_replace_words
from mizuki.admin import admin_only

@admin_only
async def add_replace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a word replacement: /arep <from> <with>"""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /arep <from> <with>")
        return
    
    original = context.args[0]
    replacement = context.args[1]
    
    replace_words = load_replace_words()
    replace_words[original] = replacement
    save_replace_words(replace_words)
    
    await update.message.reply_text(f"Replacement added: '{original}' → '{replacement}'")

@admin_only
async def remove_replace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a word replacement: /rrep <from>"""
    if not context.args:
        await update.message.reply_text("Usage: /rrep <from>")
        return
    
    original = context.args[0]
    replace_words = load_replace_words()
    
    if original in replace_words:
        del replace_words[original]
        save_replace_words(replace_words)
        await update.message.reply_text(f"Replacement removed: '{original}'")
    else:
        await update.message.reply_text(f"No replacement found for '{original}'")

def get_rep_handlers():
    return [
        CommandHandler("arep", add_replace),
        CommandHandler("rrep", remove_replace)
    ]