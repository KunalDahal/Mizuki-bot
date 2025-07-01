from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from commands.admin import admin_only
from util import get_admin_ids

@admin_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /help command showing all available commands"""
    user = update.effective_user
    message = (
        "📋 Available Commands:\n\n"
        "/a <ch_id> <last_msg_id> - Add/update channel\n"
        "/r <ch_id> - Remove channel\n"
        "/ar <word> - Add to removal list\n"
        "/rr <word> - Remove from removal list\n"
        "/l - List monitored channels\n"
        "/lr - List removal words\n"
        "/help - Show this help message\n\n"
        f"🆔 Your User ID: {user.id}"
    )
    await update.message.reply_text(message)

def get_help_handler():
    return CommandHandler("help", help_command)