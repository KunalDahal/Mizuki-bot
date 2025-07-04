import logging
import json
import os
import hashlib
import io
import asyncio
import time
import imagehash
from typing import List, Dict, Optional, Union
from collections import defaultdict
from PIL import Image
from telegram import Bot, Message, InputMediaPhoto, InputMediaVideo, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from concurrent.futures import ThreadPoolExecutor
from telethon.tl.types import MessageService
from telethon.errors import FloodWaitError

from util import (
    load_banned_words,
    HASH_FILE,
    MAX_HASH_ENTRIES,
    get_target_channel,
    get_bot_token_2,
    get_admin_ids,
    escape_markdown_v2
)
from mizuki_editor.processor import Processor

logger = logging.getLogger(__name__)

class ContentChecker:
    def __init__(self):
        self.hash_data = {}
        self.banned_words = []
        self.media_group_cache = defaultdict(list)
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.bot = Bot(token=get_bot_token_2())
        self.processor = Processor()  # Text processor
        self._load_data()

    def _load_data(self):
        """Load all necessary data files"""
        self._load_hash_data()
        self._load_banned_words()

    def _load_hash_data(self):
        """Load hash data from JSON file"""
        try:
            if os.path.exists(HASH_FILE):
                with open(HASH_FILE, 'r') as f:
                    self.hash_data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading hash data: {e}")
            self.hash_data = {}

    def _save_hash_data(self):
        """Save hash data to JSON file"""
        try:
            with open(HASH_FILE, 'w') as f:
                json.dump(self.hash_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving hash data: {e}")

    def _load_banned_words(self):
        """Load banned words from JSON file"""
        self.banned_words = load_banned_words()

    async def _generate_media_hashes(self, message: Message) -> List[Dict]:
        """Generate hashes for media content"""
        media_hashes = []
        
        if message.photo:
            try:
                largest_photo = message.photo[-1]
                file = await largest_photo.get_file()
                
                if file.file_size and file.file_size > 50_000_000:
                    logger.warning(f"Skipping large photo ({file.file_size/1_000_000:.1f}MB)")
                    return media_hashes
                    
                file_bytes = await file.download_as_bytearray()
                
                def process_image():
                    image = Image.open(io.BytesIO(file_bytes))
                    return {
                        'type': 'photo',
                        'phash': str(imagehash.phash(image)),
                        'sha256': hashlib.sha256(file_bytes).hexdigest(),
                        'md5': hashlib.md5(file_bytes).hexdigest(),
                        'file_id': largest_photo.file_id
                    }
                
                media_hashes.append(await asyncio.get_event_loop().run_in_executor(
                    self.executor, process_image
                ))
            except Exception as e:
                logger.error(f"Error processing photo: {e}")
        
        elif message.video:
            try:
                video = message.video
                file = await video.get_file()
                file_bytes = bytearray()
                
                async for chunk in file.download_as_bytearray(chunk_size=1_000_000):
                    if len(file_bytes) >= 10_000_000:  # 10MB max
                        break
                    file_bytes.extend(chunk)
                
                media_hashes.append({
                    'type': 'video',
                    'sha256': hashlib.sha256(file_bytes).hexdigest(),
                    'md5': hashlib.md5(file_bytes).hexdigest(),
                    'file_id': video.file_id
                })
            except Exception as e:
                logger.error(f"Error processing video: {e}")
        
        elif message.document:
            try:
                doc = message.document
                file = await doc.get_file()
                file_bytes = bytearray()
                
                async for chunk in file.download_as_bytearray(chunk_size=1_000_000):
                    if len(file_bytes) >= 10_000_000:  # 10MB max
                        break
                    file_bytes.extend(chunk)
                
                media_hashes.append({
                    'type': 'document',
                    'sha256': hashlib.sha256(file_bytes).hexdigest(),
                    'md5': hashlib.md5(file_bytes).hexdigest(),
                    'file_id': doc.file_id
                })
            except Exception as e:
                logger.error(f"Error processing document: {e}")
                
        return media_hashes

    def _contains_banned_words(self, text: str) -> bool:
        """Check if text contains any banned words"""
        if not text or not self.banned_words:
            return False
            
        text_lower = text.lower()
        return any(word.lower() in text_lower for word in self.banned_words)

    async def _check_duplicates(self, media_hashes: List[Dict]) -> bool:
        """Check if media hashes match any existing hashes with tolerance for phash"""
        for media in media_hashes:
            for hash_type in ['phash', 'sha256', 'md5']:
                if hash_type not in media:
                    continue
                    
                for entry in self.hash_data.values():
                    for stored_media in entry.get('media', []):
                        if hash_type not in stored_media:
                            continue
                            
                        if hash_type == 'phash':
                            # Use perceptual hash with tolerance
                            try:
                                stored_hash = imagehash.hex_to_hash(stored_media['phash'])
                                current_hash = imagehash.hex_to_hash(media['phash'])
                                if stored_hash - current_hash <= 5:  # Tolerance threshold
                                    return True
                            except Exception as e:
                                logger.error(f"Error comparing phash: {e}")
                        else:
                            # Exact match for cryptographic hashes
                            if stored_media[hash_type] == media[hash_type]:
                                return True
        return False

    async def _add_to_hash_data(self, caption: str, media_hashes: List[Dict]):
        """Add new media hashes to the hash database"""
        try:
            if len(self.hash_data) >= MAX_HASH_ENTRIES:
                oldest_key = next(iter(self.hash_data))
                self.hash_data.pop(oldest_key)
                logger.info(f"Removed oldest hash entry to maintain size limit")
            
            new_key = hashlib.md5(caption.encode()).hexdigest() if caption else media_hashes[0]['sha256']
            self.hash_data[new_key] = {
                'caption': caption,
                'media': media_hashes,
                'timestamp': int(time.time())
            }
            self._save_hash_data()
        except Exception as e:
            logger.error(f"Error adding to hash data: {e}")

    async def process_message(self, message: Message) -> Optional[Union[List[Dict], str]]:
        """Process a message through the content checker pipeline"""
        try:
            # Admin access check
            user_id = message.from_user.id if message.from_user else None
            if user_id not in get_admin_ids():
                logger.warning(f"Non-admin user {user_id} attempted direct post")
                return None
                
            if hasattr(message, 'media_group_id') and message.media_group_id:
                return await self._process_media_group(message)
            return await self._process_single_message(message)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return None

    async def _process_single_message(self, message: Message) -> Optional[Union[List[Dict], str]]:
        """Process a single message (not part of a media group)"""
        caption = message.caption or message.text or ""
        
        # Process caption through text processor
        processed_caption = await self.processor.process(caption)
        
        # Banned words check
        if self._contains_banned_words(processed_caption):
            logger.warning(f"Message contains banned words - skipping")
            return None
        
        media_hashes = await self._generate_media_hashes(message)
        
        # Handle text-only messages
        if not media_hashes and message.text:
            return processed_caption
        
        # Check for duplicates
        valid_files = []
        for media in media_hashes:
            if not await self._check_duplicates([media]):
                media['processed_caption'] = processed_caption  # Add processed caption
                valid_files.append(media)
                logger.info(f"Added valid file: {media['file_id']}")
            else:
                logger.info(f"Duplicate detected: {media['file_id']}")
        
        if not valid_files:
            logger.info("No valid files after duplicate check")
            return None
        
        # Add to hash database
        await self._add_to_hash_data(processed_caption, valid_files)
        
        return valid_files

    async def _process_media_group(self, message: Message) -> Optional[List[Dict]]:
        """Process a message that's part of a media group"""
        # Initialize cache for new media groups
        if message.media_group_id not in self.media_group_cache:
            self.media_group_cache[message.media_group_id] = []
        
        self.media_group_cache[message.media_group_id].append(message)
        
        # Only process when first message arrives
        if len(self.media_group_cache[message.media_group_id]) == 1:
            asyncio.create_task(self._process_complete_media_group(message.media_group_id))
        
        return None

    async def _process_complete_media_group(self, group_id: str):
        """Process a complete media group and prepare valid files"""
        await asyncio.sleep(2)  # Wait for all parts to arrive
        
        messages = self.media_group_cache.pop(group_id, [])
        if not messages:
            return

        # Get caption from first message that has one
        raw_caption = next((msg.caption for msg in messages if msg.caption), "")
        
        # Process caption through text processor
        processed_caption = await self.processor.process(raw_caption)
        
        # Banned words check
        if self._contains_banned_words(processed_caption):
            logger.warning(f"Media group contains banned words - skipping")
            return
        
        # Process all media in group
        all_media = []
        for msg in messages:
            media_hashes = await self._generate_media_hashes(msg)
            if media_hashes:
                all_media.extend(media_hashes)
        
        if not all_media:
            return
        
        # Filter out duplicates
        valid_files = []
        for media in all_media:
            if not await self._check_duplicates([media]):
                media['processed_caption'] = processed_caption  # Add processed caption
                valid_files.append(media)
                logger.info(f"Added valid file: {media['file_id']}")
            else:
                logger.info(f"Duplicate detected: {media['file_id']}")
        
        if not valid_files:
            logger.info(f"All media in group are duplicates - skipping")
            return
        
        # Add non-duplicates to hash database
        await self._add_to_hash_data(processed_caption, valid_files)
        
        # Forward the media group immediately
        await self.forward_media_group(valid_files)

    async def forward_media_group(self, media_list: List[Dict]):
        """Forward a media group to all target channels"""
        target_ids = get_target_channel()
        if not target_ids:
            logger.warning("No target channels configured")
            return

        for target_id in target_ids:
            try:
                # Build media group for forwarding
                media_group = []
                for i, item in enumerate(media_list):
                    if item['type'] == 'photo':
                        media_type = InputMediaPhoto
                    elif item['type'] in ['video', 'document']:
                        media_type = InputMediaVideo
                    else:
                        continue
                    
                    # Apply caption only to first item
                    caption = item.get('processed_caption') if i == 0 else None
                    parse_mode = ParseMode.MARKDOWN_V2 if caption else None
                    
                    media_group.append(media_type(
                        media=item['file_id'],
                        caption=caption,
                        parse_mode=parse_mode
                    ))
                
                await self.bot.send_media_group(
                    chat_id=target_id,
                    media=media_group
                )
                logger.info(f"Successfully forwarded media group to channel {target_id}")
            except Exception as e:
                logger.error(f"Failed to forward media group to channel {target_id}: {e}")

class Forwarder:
    def __init__(self, client, bot_username):
        self.client = client
        self.bot_username = bot_username

    async def forward_message(self, message):
        """Forward a single message or media group to the bot"""
        try:
            if isinstance(message, list):
                return await self._forward_group(message)
            return await self._forward_single(message)
        except Exception as e:
            logger.error(f"Forwarding error: {e}")
            raise

    async def _forward_single(self, message):
        """Forward a single message"""
        if isinstance(message, MessageService):
            logger.debug("Skipping service message")
            return None

        try:
            return await self.client.forward_messages(
                self.bot_username,
                message
            )
        except FloodWaitError as e:
            logger.warning(f"Flood wait required: {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return await self._forward_single(message)  # Retry

    async def _forward_group(self, messages):
        """Forward a media group while preserving its structure"""
        if not messages:
            return []

        # Filter out service messages
        valid_messages = [msg for msg in messages if not isinstance(msg, MessageService)]

        if not valid_messages:
            logger.debug("No valid messages in group")
            return []

        try:
            # Forward the entire group at once
            return await self.client.forward_messages(
                self.bot_username,
                valid_messages
            )
        except FloodWaitError as e:
            logger.warning(f"Flood wait required for group: {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return await self._forward_group(messages)  # Retry
        except Exception as e:
            logger.error(f"Group forward failed: {e}")
            
            # Fallback: try forwarding individually
            logger.info("Attempting individual forward as fallback")
            results = []
            for msg in valid_messages:
                try:
                    result = await self._forward_single(msg)
                    if result:
                        results.append(result)
                except Exception as single_error:
                    logger.error(f"Failed to forward single message: {single_error}")
            return results

    async def forward_with_retry(self, messages, max_retries=3):
        """Forward messages with retry logic"""
        if not isinstance(messages, list):
            messages = [messages]

        for attempt in range(1, max_retries + 1):
            try:
                if len(messages) > 1:
                    return await self._forward_group(messages)
                return await self._forward_single(messages[0])
            except Exception as e:
                logger.error(f"Forward attempt {attempt}/{max_retries} failed: {e}")
                if attempt < max_retries:
                    wait_time = min(2 ** attempt, 60)  # Exponential backoff
                    await asyncio.sleep(wait_time)
        
        logger.error(f"Failed to forward after {max_retries} attempts")
        return None

async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle forwarded messages from users"""
    if update.message is None:
        return

    # Initialize checker if not present
    if 'content_checker' not in context.bot_data:
        context.bot_data['content_checker'] = ContentChecker()
    
    checker = context.bot_data['content_checker']
    msg = update.message

    # Handle media groups
    if msg.media_group_id:
        # Initialize cache for new media groups
        if msg.media_group_id not in checker.media_group_cache:
            checker.media_group_cache[msg.media_group_id] = []
        
        checker.media_group_cache[msg.media_group_id].append(msg)
        
        # Only process when first message arrives
        if len(checker.media_group_cache[msg.media_group_id]) == 1:
            asyncio.create_task(checker._process_complete_media_group(msg.media_group_id))
        return
    
    # Handle single messages
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

async def forward_to_all_targets(
    context: ContextTypes.DEFAULT_TYPE,
    text: str = None,
    media: List[Dict] = None
):
    """Forward content to all target channels"""
    target_ids = get_target_channel()
    if not target_ids:
        logger.warning("No target channels configured")
        return

    for target_id in target_ids:
        try:
            if text:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            elif media:
                # For single media items
                if len(media) == 1:
                    item = media[0]
                    caption = item.get('processed_caption')
                    parse_mode = ParseMode.MARKDOWN_V2 if caption else None
                    
                    if item['type'] == 'photo':
                        await context.bot.send_photo(
                            chat_id=target_id,
                            photo=item['file_id'],
                            caption=caption,
                            parse_mode=parse_mode
                        )
                    elif item['type'] in ['video', 'document']:
                        await context.bot.send_video(
                            chat_id=target_id,
                            video=item['file_id'],
                            caption=caption,
                            parse_mode=parse_mode
                        )
                # For multiple media items (not a group)
                else:
                    media_group = []
                    for i, item in enumerate(media):
                        if item['type'] == 'photo':
                            media_type = InputMediaPhoto
                        elif item['type'] in ['video', 'document']:
                            media_type = InputMediaVideo
                        else:
                            continue
                        
                        # Apply caption only to first item
                        caption = item.get('processed_caption') if i == 0 else None
                        parse_mode = ParseMode.MARKDOWN_V2 if caption else None
                        
                        media_group.append(media_type(
                            media=item['file_id'],
                            caption=caption,
                            parse_mode=parse_mode
                        ))
                    
                    await context.bot.send_media_group(
                        chat_id=target_id,
                        media=media_group
                    )
        except Exception as e:
            logger.error(f"Failed to forward to channel {target_id}: {e}")