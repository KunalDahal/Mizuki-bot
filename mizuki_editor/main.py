# main.py
import logging
import asyncio
import time
import random
from asyncio import Lock
from telegram import Update
from telegram.ext import ContextTypes
from mizuki_editor.content_checker import ContentChecker
from mizuki_editor.forward import forward_to_all_targets
from collections import deque

logger = logging.getLogger(__name__)

message_queue = []
queue_lock = Lock()

class RateLimiter:
    def __init__(self, max_calls, period):
        self.max_calls = max_calls
        self.period = period
        self.timestamps = deque(maxlen=max_calls)
        
    async def wait(self):
        now = time.time()
        if len(self.timestamps) >= self.max_calls:
            elapsed = now - self.timestamps[0]
            if elapsed < self.period:
                wait_time = self.period - elapsed
                logger.debug(f"Rate limited - waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time * random.uniform(0.8, 1.2))
        self.timestamps.append(now)

async def worker(context: ContextTypes.DEFAULT_TYPE):
    if 'rate_limiter' not in context.bot_data:
        context.bot_data['rate_limiter'] = RateLimiter(20, 60)
    
    while True:
        await context.bot_data['rate_limiter'].wait()
        
        async with queue_lock:
            if not message_queue:
                context.bot_data["worker_started"] = False
                logger.debug("Worker stopping - queue empty")
                return
            
            message_queue.sort(key=lambda u: u.message.date.timestamp() 
                              if u.message and u.message.date else 0)
            update = message_queue.pop(0)
        
        try:
            if 'content_checker' not in context.bot_data:
                context.bot_data['content_checker'] = ContentChecker()
            
            checker = context.bot_data['content_checker']
            msg = update.message

            result = await checker.process_message(msg)
            if result is None:
                continue
                
            if isinstance(result, str):
                await forward_to_all_targets(context, text=result)
            elif isinstance(result, list):
                await forward_to_all_targets(context, media=result)
                
        except Exception as e:
            logger.error(f"Error handling queued message: {e}")
            if update.message:
                try:
                    await update.message.reply_text("⚠️ Error processing your message. Please try again.")
                except Exception as reply_error:
                    logger.error(f"Failed to send error reply: {reply_error}")

async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return

    async with queue_lock:
        message_queue.append(update)
        queue_size = len(message_queue)
    
    logger.info(f"Message added to queue (size: {queue_size})")
    
    if not context.bot_data.get("worker_started", False):
        context.bot_data["worker_started"] = True
        asyncio.create_task(worker(context))
        logger.info("Started new worker for message processing")