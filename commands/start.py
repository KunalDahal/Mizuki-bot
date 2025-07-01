from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from commands.admin import admin_only

@admin_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Concise start command as requested"""
    user = update.effective_user
    message = f"👋 Hey Admin {user.first_name}!"
    await update.message.reply_text(message)

def get_start_handler():
    return CommandHandler("start", start_command)