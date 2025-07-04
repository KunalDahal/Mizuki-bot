import asyncio
import logging
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from collections import defaultdict
from util import get_target_channel
from typing import List, Union

logger = logging.getLogger(__name__)

# Global state for media groups
MEDIA_GROUPS = defaultdict(list)
processing_semaphore = asyncio.Semaphore(1) 

async def process_media_group(group_id: str, context: ContextTypes.DEFAULT_TYPE):
    """Process a media group with proper synchronization"""
    async with processing_semaphore:
        messages = MEDIA_GROUPS.pop(group_id, [])
        if not messages:
            return

        # Verify admin
        if messages[0].from_user.id not in context.bot_data.get('admin_ids', []):
            logger.warning(f"Non-admin attempted to send media group: {messages[0].from_user.id}")
            return

        processor = context.bot_data.get('processor')
        if not processor:
            logger.error("Processor not properly initialized")
            return

        try:
            # Find caption from the first message that has one
            caption = next((msg.caption for msg in messages if msg.caption), None)
            processed_content = await processor.process(caption) if caption else None

            # Prepare media group for forwarding
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

                media_group.append(media_type(
                    media=file_id,
                    caption=processed_content if i == 0 else None,
                    parse_mode=ParseMode.MARKDOWN_V2 if i == 0 and processed_content else None
                ))

            if media_group:
                await forward_to_all_targets(context, media_group=media_group)

        except Exception as e:
            logger.error(f"Failed to process media group {group_id}: {e}")

async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages from admin with proper synchronization"""
    if update.message is None:
        return

    # Verify admin
    if update.message.from_user.id not in context.bot_data.get('admin_ids', []):
        logger.warning(f"Non-admin message attempt from: {update.message.from_user.id}")
        return

    async with processing_semaphore:
        msg = update.message
        processor = context.bot_data.get('processor')
        
        if not processor:
            logger.error("Processor not properly initialized")
            return

        # Handle media groups
        if hasattr(msg, 'media_group_id') and msg.media_group_id:
            MEDIA_GROUPS[msg.media_group_id].append(msg)
            if len(MEDIA_GROUPS[msg.media_group_id]) == 1:  # Only schedule processing once
                asyncio.create_task(process_media_group(msg.media_group_id, context))
            return

        # Handle single messages
        try:
            content = msg.caption or msg.text or ""
            processed_content = await processor.process(content)

            if msg.photo:
                await forward_to_all_targets(context, photo=msg.photo[-1].file_id, caption=processed_content)
            elif msg.video:
                await forward_to_all_targets(context, video=msg.video.file_id, caption=processed_content)
            elif msg.text:
                await forward_to_all_targets(context, text=processed_content)

        except Exception as e:
            logger.error(f"Failed to handle message: {e}")

async def forward_to_all_targets(
    context: ContextTypes.DEFAULT_TYPE,
    text: str = None,
    photo: str = None,
    video: str = None,
    media_group: List[Union[InputMediaPhoto, InputMediaVideo]] = None,
    caption: str = None
):
    """Forward content to all target channels"""
    target_ids = get_target_channel()
    if not target_ids:
        logger.warning("No target channels configured")
        return

    for target_id in target_ids:
        try:
            if media_group:
                await context.bot.send_media_group(
                    chat_id=target_id,
                    media=media_group
                )
            elif photo:
                await context.bot.send_photo(
                    chat_id=target_id,
                    photo=photo,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            elif video:
                await context.bot.send_video(
                    chat_id=target_id,
                    video=video,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            elif text:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
        except Exception as e:
            logger.error(f"Failed to forward to channel {target_id}: {e}")