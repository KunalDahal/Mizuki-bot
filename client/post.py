import json
import os
from telegram import InputMediaPhoto, InputMediaVideo,Update,InlineKeyboardButton,InlineKeyboardMarkup,MessageOriginChannel,MessageOriginChat
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import asyncio
from util import get_moderation_channel_id,get_target_channel_id,POST_FILE,generate_post_id
import logging
from datetime import datetime
from collections import defaultdict
from telegram.helpers import escape_markdown
from edit.processor import Processor
import random

logger = logging.getLogger(__name__)
MEDIA_GROUPS = defaultdict(list)
processing_lock = asyncio.Lock()
button_queue = asyncio.Queue()
worker_task = None

async def button_worker():
    while True:
        (update, context) = await button_queue.get()
        try:
            # Process the button action
            await process_button_action(update, context)
        finally:
            button_queue.task_done()

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global worker_task
    if worker_task is None:
        worker_task = asyncio.create_task(button_worker())
    
    await button_queue.put((update, context))
    await update.callback_query.answer("Request received, processing...")

async def clean_up_post(context, post_id, post_data):
    mod_channel = get_moderation_channel_id()
    
    # Delete from moderation channel
    for msg_id in post_data['msg_ids']:
        try:
            await context.bot.delete_message(mod_channel, msg_id)
        except Exception as e:
            logger.error(f"Error deleting message {msg_id}: {e}")
    
    # Delete notification message
    try:
        # We need to store notification message ID in post_data
        if 'notification_id' in post_data:
            await context.bot.delete_message(mod_channel, post_data['notification_id'])
    except Exception as e:
        logger.error(f"Error deleting notification: {e}")
    
    # Update storage
    update_post_store(post_id, None, "remove")
    
async def process_button_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    parts = data.split('_')
    action = parts[0]
    post_id = int(parts[1])
    mod_channel = get_moderation_channel_id()
    
    # Load post data from storage
    try:
        with open(POST_FILE, 'r') as f:
            store = json.load(f)
        post_data = store.get(str(post_id))
        
        if not post_data:
            await query.edit_message_text(text="⚠️ Post data not found")
            return
    except Exception as e:
        logger.error(f"Error loading post store: {e}")
        return

    try:
        if action == 'decline':
            # Delete all messages in the group
            for msg_id in post_data['msg_ids']:
                try:
                    await context.bot.delete_message(mod_channel, msg_id)
                except Exception as e:
                    logger.error(f"Error deleting message {msg_id}: {e}")
            
            # Delete notification message
            try:
                await query.message.delete()
            except Exception as e:
                logger.error(f"Error deleting notification: {e}")
            
            # Update storage
            update_post_store(post_id, None, "remove")
            logger.info(f"Declined post {post_id}")

        elif action == 'approve':
            # Update notification
            await query.message.edit_text(
                text=f"✅ Approved by {query.from_user.first_name}",
                reply_markup=None
            )
            
            # Initialize Processor
            processor = Processor()
            target_channel = get_target_channel_id()
            
            # Process and forward content
            if post_data['is_group']:
                # Process combined caption
                original_caption = post_data.get('combined_caption', '')
                processed_caption = processor.process(original_caption)
                
                # Create media group with processed caption
                media_group = []
                for i, media in enumerate(post_data['content']):
                    if media['type'] == 'photo':
                        media_type = InputMediaPhoto
                    elif media['type'] == 'video':
                        media_type = InputMediaVideo
                    else:
                        continue
                    
                    # Apply processed caption only to first media item
                    caption = processed_caption if i == 0 else None
                    media_group.append(media_type(
                        media=media['file_id'],
                        caption=caption,
                        parse_mode=ParseMode.MARKDOWN_V2 if caption else None
                    ))
                
                # Send media group to target channel
                await context.bot.send_media_group(
                    chat_id=target_channel,
                    media=media_group
                )
            else:
                # Handle single message
                media = post_data['content'][0]
                original_content = media.get('caption') or media.get('text') or ''
                processed_content = processor.process(original_content)
                
                if media['type'] == 'text':
                    await context.bot.send_message(
                        chat_id=target_channel,
                        text=processed_content,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                elif media['type'] == 'photo':
                    await context.bot.send_photo(
                        chat_id=target_channel,
                        photo=media['file_id'],
                        caption=processed_content,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                elif media['type'] == 'video':
                    await context.bot.send_video(
                        chat_id=target_channel,
                        video=media['file_id'],
                        caption=processed_content,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
            
            # Wait 5 seconds then clean up
            await asyncio.sleep(5)
            
            # Delete from moderation channel
            for msg_id in post_data['msg_ids']:
                try:
                    await context.bot.delete_message(mod_channel, msg_id)
                except:
                    pass
            
            # Delete notification message
            try:
                await query.message.delete()
            except:
                pass
            
            # Update storage
            update_post_store(post_id, None, "remove")
            logger.info(f"Approved post {post_id}")
            
    except Exception as e:
        logger.error(f"Button action failed: {e}")
        await query.edit_message_text(text=f"⚠️ Error: {e}")
        
def update_post_store(post_id, data, action="add"):
    try:
        # Create storage directory if not exists
        os.makedirs(os.path.dirname(POST_FILE), exist_ok=True)
        
        if not os.path.exists(POST_FILE):
            with open(POST_FILE, 'w') as f:
                json.dump({}, f)
        
        with open(POST_FILE, 'r') as f:
            store = json.load(f)
        
        if action == "add":
            store[str(post_id)] = data
        elif action == "remove":
            store.pop(str(post_id), None)
        
        with open(POST_FILE, 'w') as f:
            json.dump(store, f, indent=2)
    except Exception as e:
        logger.error(f"Post store error: {e}")

async def process_media_group(group_id, context, update):
    async with processing_lock:
        await asyncio.sleep(2.0)
        messages = MEDIA_GROUPS.pop(group_id, [])
        
        if not messages:
            return
        
        mod_channel = get_moderation_channel_id()
        
        try:
            # Collect all captions in the group
            captions = []
            for msg in messages:
                if msg.caption:
                    # Escape Markdown special characters
                    captions.append(escape_markdown(msg.caption, version=2))
            
            # Combine all captions into one
            combined_caption = "\n\n".join(captions) if captions else None
            
            # Build media group for forwarding
            media_group = []
            for i, msg in enumerate(messages):
                if msg.photo:
                    # Add caption only to the first media item
                    caption = combined_caption if i == 0 else None
                    media_group.append(InputMediaPhoto(
                        media=msg.photo[-1].file_id,
                        caption=caption,
                        parse_mode=ParseMode.MARKDOWN_V2 if caption else None
                    ))
                elif msg.video:
                    # Add caption only to the first media item
                    caption = combined_caption if i == 0 else None
                    media_group.append(InputMediaVideo(
                        media=msg.video.file_id,
                        caption=caption,
                        parse_mode=ParseMode.MARKDOWN_V2 if caption else None
                    ))
            
            # Send media group to moderation channel
            sent_messages = await context.bot.send_media_group(
                chat_id=mod_channel,
                media=media_group
            )
            
            # Get message IDs
            msg_ids = [m.message_id for m in sent_messages]
            
            # Generate unique post ID
            post_id = generate_post_id()
            
            # Store content for later approval
            content = []
            for msg in messages:
                media_data = {
                    'type': 'photo' if msg.photo else 'video',
                    'file_id': msg.photo[-1].file_id if msg.photo else msg.video.file_id,
                    'caption': msg.caption  # Store original caption
                }
                content.append(media_data)
            
            # Store post data
            post_data = {
                'msg_ids': msg_ids,
                'content': content,
                'is_group': True,
                'timestamp': datetime.now().isoformat(),
                'combined_caption': combined_caption  # Store the combined caption
            }
            update_post_store(post_id, post_data)
            
            # Get source info
            source_name = "Unknown"
            if messages[0].forward_origin:
                if isinstance(messages[0].forward_origin, MessageOriginChannel):
                    source_name = messages[0].forward_origin.chat.title
                elif isinstance(messages[0].forward_origin, MessageOriginChat):
                    source_name = messages[0].forward_origin.sender_chat.title
            
            # Create buttons with post ID
            keyboard = [[
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{post_id}"),
                InlineKeyboardButton("❌ Decline", callback_data=f"decline_{post_id}")
            ]]
            
            # Send notification
            await context.bot.send_message(
                chat_id=mod_channel,
                text=f"New album from {source_name} (ID: {post_id}):",
                reply_markup=InlineKeyboardMarkup(keyboard))
                
        except Exception as e:
            logger.error(f"Failed to process media group: {e}")
        finally:
            # Clean up timers
            if hasattr(context, 'media_group_timers') and group_id in context.media_group_timers:
                del context.media_group_timers[group_id]

async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with processing_lock:    
        msg = update.message
        mod_channel = get_moderation_channel_id()
        
        # Handle media groups with timer reset
        if msg.media_group_id:
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
            # Escape caption if exists
            caption = None
            if msg.caption:
                caption = escape_markdown(msg.caption, version=2)
            
            sent = None
            
            if msg.photo:
                sent = await context.bot.send_photo(
                    chat_id=mod_channel,
                    photo=msg.photo[-1].file_id,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN_V2 if caption else None
                )
                
            elif msg.video:
                sent = await context.bot.send_video(
                    chat_id=mod_channel,
                    video=msg.video.file_id,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN_V2 if caption else None
                )
                
            elif msg.text:
                # Escape text for Markdown
                text = escape_markdown(msg.text, version=2)
                sent = await context.bot.send_message(
                    chat_id=mod_channel,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            else:
                return
            
            if not sent:
                return
                
            # Prepare content storage
            content = [{
                'type': 'photo' if msg.photo else 'video' if msg.video else 'text',
                'file_id': msg.photo[-1].file_id if msg.photo else msg.video.file_id if msg.video else None,
                'caption': msg.caption,
                'text': msg.text if msg.text else None
            }]
            
            # Generate unique post ID
            post_id = generate_post_id()
            
            # Store post data
            post_data = {
                'msg_ids': [sent.message_id],
                'content': content,
                'is_group': False,
                'timestamp': datetime.now().isoformat()
            }
            update_post_store(post_id, post_data)
            
            # Get source info
            source_name = "Unknown"
            if msg.forward_origin:
                if isinstance(msg.forward_origin, MessageOriginChannel):
                    source_name = msg.forward_origin.chat.title
                elif isinstance(msg.forward_origin, MessageOriginChat):
                    source_name = msg.forward_origin.sender_chat.title
            
            # Create buttons
            keyboard = [[
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{post_id}"),
                InlineKeyboardButton("❌ Decline", callback_data=f"decline_{post_id}")
            ]]
            
            # Send notification
            await context.bot.send_message(
                chat_id=mod_channel,
                text=f"New post from {source_name} (ID: {post_id}):",
                reply_markup=InlineKeyboardMarkup(keyboard))
                
        except Exception as e:
            logger.error(f"Failed to handle message: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    parts = data.split('_')
    action = parts[0]
    post_id = int(parts[1])
    mod_channel = get_moderation_channel_id()
    
    # Load post data from storage
    try:
        with open(POST_FILE, 'r') as f:
            store = json.load(f)
        post_data = store.get(str(post_id))
        
        if not post_data:
            await query.edit_message_text(text="⚠️ Post data not found")
            return
    except Exception as e:
        logger.error(f"Error loading post store: {e}")
        return

    try:
        if action == 'decline':
            # Delete all messages in the group
            for msg_id in post_data['msg_ids']:
                try:
                    await context.bot.delete_message(mod_channel, msg_id)
                except Exception as e:
                    logger.error(f"Error deleting message {msg_id}: {e}")
            
            # Delete notification message
            try:
                await query.message.delete()
            except Exception as e:
                logger.error(f"Error deleting notification: {e}")
            
            # Update storage
            update_post_store(post_id, None, "remove")
            logger.info(f"Declined post {post_id}")

        elif action == 'approve':
            # Update notification
            await query.message.edit_text(
                text=f"✅ Approved by {query.from_user.first_name}",
                reply_markup=None
            )
            
            # Initialize Processor
            processor = Processor()
            target_channel = get_target_channel_id()
            bot_token = context.bot.token  # Get bot token from context
            
            # Process and forward content
            if post_data['is_group']:
                # Process combined caption
                original_caption = post_data.get('combined_caption', '')
                processed_caption = processor.process(original_caption)
                
                # Create media group with processed caption
                media_group = []
                for i, media in enumerate(post_data['content']):
                    if media['type'] == 'photo':
                        media_type = InputMediaPhoto
                    elif media['type'] == 'video':
                        media_type = InputMediaVideo
                    else:
                        continue
                    
                    # Apply processed caption only to first media item
                    caption = processed_caption if i == 0 else None
                    media_group.append(media_type(
                        media=media['file_id'],
                        caption=caption,
                        parse_mode=ParseMode.MARKDOWN_V2 if caption else None
                    ))
                
                # Send media group to target channel
                await context.bot.send_media_group(
                    chat_id=target_channel,
                    media=media_group
                )
            else:
                # Handle single message
                media = post_data['content'][0]
                original_content = media.get('caption') or media.get('text') or ''
                processed_content = processor.process(original_content)
                
                if media['type'] == 'text':
                    await context.bot.send_message(
                        chat_id=target_channel,
                        text=processed_content,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                elif media['type'] == 'photo':
                    await context.bot.send_photo(
                        chat_id=target_channel,
                        photo=media['file_id'],
                        caption=processed_content,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                elif media['type'] == 'video':
                    await context.bot.send_video(
                        chat_id=target_channel,
                        video=media['file_id'],
                        caption=processed_content,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
            
            # Add delay here - after forwarding but before cleanup
            base_delay = 5
            jitter = random.uniform(0, 3)  # 0-3 seconds jitter
            await asyncio.sleep(base_delay + jitter)
            
            # Cleanup after delay
            for msg_id in post_data['msg_ids']:
                try:
                    await context.bot.delete_message(mod_channel, msg_id)
                except:
                    pass
            
            try:
                await query.message.delete()
            except:
                pass
            
            update_post_store(post_id, None, "remove")
            logger.info(f"Approved post {post_id}")
            
    except Exception as e:
        logger.error(f"Button action failed: {e}")
        await query.edit_message_text(text=f"⚠️ Error: {e}")