import json
import os
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from mizuki.admin import admin_only
from util import load_remove_words,save_remove_words


@admin_only
async def remove_remove_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /rr <word or phrase>")
        return

    word = " ".join(context.args).strip().lower()
    if not word:
        await update.message.reply_text("❌ Error: Please provide a valid word or phrase")
        return

    try:
        words = load_remove_words()
        
        if word not in words:
            await update.message.reply_text(f"⚠️ '{word}' not found in removal list")
            return
            
        words.remove(word)
        save_remove_words(words)
        
        await update.message.reply_text(f"✅ Removed from list: '{word}'")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

@admin_only
async def add_remove_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /ar <word or phrase>")
        return

    word = " ".join(context.args).strip().lower()
    if not word:
        await update.message.reply_text("❌ Error: Please provide a valid word or phrase")
        return

    try:
        words = load_remove_words()
        
        if word in words:
            await update.message.reply_text(f"⚠️ '{word}' is already in the removal list")
            return
            
        words.append(word)
        save_remove_words(words)
        
        await update.message.reply_text(f"✅ Added to removal list: '{word}'")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

def get_add_remove_word_handler():
    return CommandHandler("ar", add_remove_word_command)
def get_remove_remove_word_handler():
    return CommandHandler("rr", remove_remove_word_command)