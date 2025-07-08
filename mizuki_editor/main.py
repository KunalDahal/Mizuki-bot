import logging
import asyncio
from collections import deque
from asyncio import Lock
from telegram import Update
from telegram.ext import ContextTypes
from mizuki_editor.content_checker import ContentChecker
from mizuki_editor.forward import forward_to_all_targets

logger = logging.getLogger(__name__)

# Global queue and lock for message processing
message_queue = deque()
queue_lock = Lock()

async def worker(context: ContextTypes.DEFAULT_TYPE):
    """Worker to process messages from the queue one by one"""
    while True:
        # Get next message from queue
        async with queue_lock:
            if not message_queue:
                # Reset worker flag when queue is empty
                context.bot_data["worker_started"] = False
                return
            update = message_queue.popleft()
        
        try:
            # Initialize checker if not present
            if 'content_checker' not in context.bot_data:
                context.bot_data['content_checker'] = ContentChecker()
            
            checker = context.bot_data['content_checker']
            msg = update.message

            # Process the message through content checker
            result = await checker.process_message(msg)
            if result is None:
                continue
                
            # Forward based on result type
            if isinstance(result, str):  # Text message
                await forward_to_all_targets(context, text=result)
            elif isinstance(result, list):  # Media message
                await forward_to_all_targets(context, media=result)
                
        except Exception as e:
            logger.error(f"Error handling queued message: {e}")
            if update.message:
                await update.message.reply_text("⚠️ Error processing your message. Please try again.")

async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle forwarded messages from users by adding to processing queue"""
    if update.message is None:
        return

    # Add message to processing queue
    async with queue_lock:
        message_queue.append(update)
    
    # Start worker if not already running
    if not context.bot_data.get("worker_started", False):
        context.bot_data["worker_started"] = True
        asyncio.create_task(worker(context))
        logger.info("Started new worker for message processing")