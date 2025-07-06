import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from mizuki_editor.content_checker import ContentChecker
from mizuki_editor.forward import forward_to_all_targets

logger = logging.getLogger(__name__)

async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle forwarded messages from users"""
    if update.message is None:
        return

    # Initialize checker if not present
    if 'content_checker' not in context.bot_data:
        context.bot_data['content_checker'] = ContentChecker()
    
    checker = context.bot_data['content_checker']
    msg = update.message

    try:
        result = await checker.process_message(msg)
        if result is None:
            return
            
        if isinstance(result, str):  # Text message
            await forward_to_all_targets(context, text=result)
        elif isinstance(result, list):  # Media message
            await forward_to_all_targets(context, media=result)
            
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        if update.message:
            await update.message.reply_text("⚠️ Error processing your message. Please try again.")