from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from util import load_banned_words, save_banned_words
from commands.admin import admin_only
import logging

logger = logging.getLogger(__name__)

@admin_only
async def add_banned_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add words to the banned list"""
    if not context.args:
        await update.message.reply_text("Usage: /ab word1 word2 ...")
        return
    
    words_to_add = context.args
    banned_words = load_banned_words()
    added_words = []
    
    for word in words_to_add:
        if word not in banned_words:
            banned_words.append(word)
            added_words.append(word)
    
    save_banned_words(banned_words)
    
    if added_words:
        await update.message.reply_text(f"Added banned words: {', '.join(added_words)}")
    else:
        await update.message.reply_text("No new words were added (they were already banned)")

@admin_only
async def remove_banned_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove words from the banned list"""
    if not context.args:
        await update.message.reply_text("Usage: /rb word1 word2 ...")
        return
    
    words_to_remove = context.args
    banned_words = load_banned_words()
    removed_words = []
    
    for word in words_to_remove:
        if word in banned_words:
            banned_words.remove(word)
            removed_words.append(word)
    
    save_banned_words(banned_words)
    
    if removed_words:
        await update.message.reply_text(f"Removed banned words: {', '.join(removed_words)}")
    else:
        await update.message.reply_text("None of these words were in the banned list")

def get_banned_handlers():
    return [
        CommandHandler("ab", add_banned_word),
        CommandHandler("rb", remove_banned_word)
    ]