import os
import json
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from mizuki.admin import admin_only
from mizuki.config import save_upvotes,load_upvotes

async def upvote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /upvote command"""
    user = update.effective_user
    if not user:
        await update.message.reply_text("❌ Could not identify user.")
        return

    upvote_data = load_upvotes()
    
    if str(user.id) in upvote_data["users"]:
        await update.message.reply_text("👍 You've already upvoted! Thanks for your support!")
        return
    
    upvote_data["users"][str(user.id)] = {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name
    }
    upvote_data["count"] += 1
    
    if save_upvotes(upvote_data):
        message = (
            "✅ Thank you for your upvote!\n\n"
            f"👤 User: {user.full_name}\n"
            f"🆔 ID: {user.id}\n"
            f"📛 Username: @{user.username if user.username else 'N/A'}\n"
            f"👍 Total Upvotes: {upvote_data['count']}"
        )
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("❌ Failed to save your upvote. Please try again.")

@admin_only
async def upvote_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /upvote_count command (admin only)"""
    upvote_data = load_upvotes()
    count = upvote_data.get("count", 0)
    unique_voters = len(upvote_data.get("users", {}))
    
    message = (
        "📊 Upvote Statistics:\n\n"
        f"👍 Total Upvotes: {count}\n"
        f"👥 Unique Voters: {unique_voters}"
    )
    
    await update.message.reply_text(message)

def get_upvote_handlers():
    """Return upvote command handlers"""
    return [
        CommandHandler("upvote", upvote),
        CommandHandler("upvote_count", upvote_count)
    ]