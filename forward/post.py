import asyncio
import logging
import random
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from collections import defaultdict
from util import get_target_channel_id

logger = logging.getLogger(__name__)
MEDIA_GROUPS = defaultdict(list)
processing_lock = asyncio.Lock()

last_forward_time = 0
forward_lock = asyncio.Lock()
MIN_FORWARD_INTERVAL = 15  # seconds

async def forward_with_delay(context, send_func, *args, **kwargs):
    global last_forward_time
    async with forward_lock:
        now = asyncio.get_event_loop().time()
        wait_time = max(0, MIN_FORWARD_INTERVAL - (now - last_forward_time))
        jitter = random.uniform(0, 3)
        await asyncio.sleep(wait_time + jitter)
        
        try:
            await send_func(*args, **kwargs)
        finally:
            last_forward_time = asyncio.get_event_loop().time()

        
async def process_media_group(group_id, context, update):
    async with processing_lock:
        await asyncio.sleep(2.0) 
        messages = MEDIA_GROUPS.pop(group_id, [])
        
        if not messages:
            return
            
        processor = context.bot_data.get('processor')
        if not processor:
            logger.error("Processor not properly initialized")
            return
            
        target_channel = get_target_channel_id()
        bot = context.bot
        
        try:
            # Find the first message with a caption in the media group
            caption = None
            for msg in messages:
                if msg.caption:
                    caption = msg.caption
                    break
            
            processed_content = await processor.process(caption) if caption else None
            
            if processed_content is None:
                logger.info(f"Skipping media group {group_id} after processing")
                return
            
            # Forward media group
            media_group = []
            for i, msg in enumerate(messages):
                if msg.photo:
                    media_type = InputMediaPhoto
                    file_id = msg.photo[-1].file_id
                elif msg.video:
                    media_type = InputMediaVideo
                    file_id = msg.video.file_id
                else:
                    continue
                
                # Only add caption to the first media item
                media_group.append(media_type(
                    media=file_id,
                    caption=processed_content if i == 0 else None,
                    parse_mode=ParseMode.MARKDOWN_V2 if i == 0 and processed_content else None
                ))
            
            try:
                await forward_with_delay(
                    context,
                    bot.send_media_group,
                    chat_id=target_channel,
                    media=media_group
                )
                
            except Exception as e:
                logger.error(f"Failed to forward media group {group_id}: {e}")
                # Don't add to training data if forwarding failed
                return
            
        except Exception as e:
            logger.error(f"Failed to process media group {group_id}: {e}")
        finally:
            # Clean up timers
            if hasattr(context, 'media_group_timers') and group_id in context.media_group_timers:
                del context.media_group_timers[group_id]
                
async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Early return if no message
    if update.message is None:
        logger.debug("Received forwarded update with no message content")
        return

    async with processing_lock:    
        msg = update.message
        processor = context.bot_data.get('processor')
        
        if not processor:
            logger.error("Processor not properly initialized")
            return
            
        target_channel = get_target_channel_id()
        bot = context.bot
        
        # Handle media groups
        if hasattr(msg, 'media_group_id') and msg.media_group_id:
            MEDIA_GROUPS[msg.media_group_id].append(msg)
            
            # Reset timer on each new message
            if not hasattr(context, 'media_group_timers'):
                context.media_group_timers = {}
                
            # Cancel existing timer if any
            if msg.media_group_id in context.media_group_timers:
                context.media_group_timers[msg.media_group_id].cancel()
            
            # Create new timer
            context.media_group_timers[msg.media_group_id] = asyncio.create_task(
                process_media_group(msg.media_group_id, context, update)
            )
            return
        
        # Handle single messages
        try:
            # Process content
            content = msg.caption or msg.text or ""
            processed_content = await processor.process(content)
            
            # Forward based on media type
            if msg.photo:
                await forward_with_delay(
                    context,
                    bot.send_photo,
                    chat_id=target_channel,
                    photo=msg.photo[-1].file_id,
                    caption=processed_content,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            elif msg.video:
                await forward_with_delay(
                    context,
                    bot.send_video,
                    chat_id=target_channel,
                    video=msg.video.file_id,
                    caption=processed_content,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            elif msg.text:
                await forward_with_delay(
                    context,
                    bot.send_message,
                    chat_id=target_channel,
                    text=processed_content,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                
        except Exception as e:
            logger.error(f"Failed to handle message: {e}")