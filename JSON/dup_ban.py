import logging
from typing import Dict, List
from telegram import Message, Update, InputMediaVideo, InputMediaPhoto
from telegram.ext import MessageHandler, filters, ContextTypes
import os
from util import (
    load_banned_words,
    HASH_FILE,
    MAX_HASH_ENTRIES,
    get_target_channel,
    load_channels
)
from telegram.constants import ParseMode
from mizuki_editor.processor import Processor
import json
from PIL import Image
import imagehash
import hashlib
import io
import asyncio

logger = logging.getLogger(__name__)

class DupBanMonitor:
    def __init__(self, application, dump_channel_id: int):
        self.application = application
        self.bot = application.bot
        self.hash_data = {}
        self.banned_words = []
        self.source_channel_ids = load_channels()  # Monitor source channels, not target
        self.dump_channel_id = dump_channel_id
        self.processing_semaphore = asyncio.Semaphore(1)
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

    async def start(self):
        """Start monitoring the SOURCE channels for new messages"""
        for channel_id in self.source_channel_ids:
            self.application.add_handler(
                MessageHandler(
                    filters.Chat(channel_id) & 
                    (filters.PHOTO | filters.VIDEO),
                    self._process_message
                )
            )
        logger.info("DupBan monitor started for source channels")

    async def _process_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process incoming messages from source channels"""
        message = update.effective_message
        if not message:
            return

        async with self.processing_semaphore:
            try:
                # Check for banned words first
                caption = message.caption or ""
                if self._contains_banned_words(caption):
                    logger.info("Message contains banned words")
                    await self._handle_invalid(message, "banned words")
                    return

                # Generate hashes for all media in this message
                media_hashes = await self._generate_media_hashes(message)
                logger.debug(f"Generated hashes: {media_hashes}")

                if not media_hashes:
                    logger.debug("No valid media found in message")
                    return  # No valid media, nothing to do

                # If it's a single media message
                if len(media_hashes) == 1:
                    duplicate_info = self._find_duplicate(media_hashes[0])
                    if duplicate_info:
                        logger.info("Single media message is duplicate")
                        await self._handle_invalid(message, "duplicate")
                        # Delete the original duplicate message
                        await self._delete_original_duplicate(duplicate_info['message_id'], duplicate_info['file_id'])
                    else:
                        logger.info("Single media message is valid - storing hashes")
                        self._store_hashes(message.message_id, media_hashes)
                        await self._send_to_target(message, media_hashes[0], caption)
                    return

                # For media groups
                duplicate_found = False
                non_duplicate_media = []
                
                for media in media_hashes:
                    duplicate_info = self._find_duplicate(media)
                    if duplicate_info:
                        duplicate_found = True
                        # Delete the original duplicate message
                        await self._delete_original_duplicate(duplicate_info['message_id'], duplicate_info['file_id'])
                    else:
                        non_duplicate_media.append(media)

                if duplicate_found and not non_duplicate_media:
                    logger.info("All media in group are duplicates")
                    await self._handle_invalid(message, "duplicate")
                    return
                
                # If at least one media is not duplicate, forward all to target
                logger.info("At least one media is not duplicate - forwarding to target")
                self._store_hashes(message.message_id, non_duplicate_media)
                
                if len(non_duplicate_media) == 1:
                    await self._send_to_target(message, non_duplicate_media[0], caption)
                else:
                    await self._send_group_to_target(message, non_duplicate_media)

            except Exception as e:
                logger.error(f"Unhandled error processing message {getattr(message, 'message_id', 'unknown')}: {e}", exc_info=True)

    async def _delete_original_duplicate(self, original_message_id: int, file_id: str):
        """Delete the original duplicate message from target channel"""
        try:
            target_channel = get_target_channel()
            if not target_channel:
                logger.error("No target channel configured!")
                return
                
            # Try to delete the message containing this file
            await self.bot.delete_message(
                chat_id=target_channel,
                message_id=original_message_id
            )
            logger.info(f"Deleted duplicate message {original_message_id} from target channel")
        except Exception as e:
            logger.error(f"Failed to delete duplicate message {original_message_id}: {str(e)}")

    def _contains_banned_words(self, text: str) -> bool:
        """Check if text contains any banned words"""
        if not text or not self.banned_words:
            return False
        text_lower = text.lower()
        return any(word.lower() in text_lower for word in self.banned_words)

    def _find_duplicate(self, media: Dict) -> Dict:
        """Find if a single media item is a duplicate and return its info"""
        for message_id, stored_media_list in self.hash_data.items():
            for stored_media in stored_media_list:
                if stored_media['type'] != media['type']:
                    continue
                
                # Exact match for videos
                if media['type'] == 'video' and media['sha256'] == stored_media['sha256']:
                    return {
                        'message_id': int(message_id),
                        'file_id': stored_media['file_id']
                    }
                
                # Photo comparison
                if media['type'] == 'photo':
                    if media['sha256'] == stored_media['sha256']:
                        return {
                            'message_id': int(message_id),
                            'file_id': stored_media['file_id']
                        }
                    try:
                        h1 = imagehash.hex_to_hash(media['phash'])
                        h2 = imagehash.hex_to_hash(stored_media['phash'])
                        if h1 - h2 < 5:  # Fuzzy match
                            return {
                                'message_id': int(message_id),
                                'file_id': stored_media['file_id']
                            }
                    except Exception as e:
                        logger.error(f"Error comparing image hashes: {e}")
        return None

    async def _handle_invalid(self, message: Message, reason: str):
        """Forward invalid message to dump channel"""
        try:
            caption = message.caption or ""
            processor = Processor()
            processed_caption = await processor.process(caption)
            
            if message.photo:
                await self.bot.send_photo(
                    chat_id=self.dump_channel_id,
                    photo=message.photo[-1].file_id,
                    caption=processed_caption,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            elif message.video:
                await self.bot.send_video(
                    chat_id=self.dump_channel_id,
                    video=message.video.file_id,
                    caption=processed_caption,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            else:
                await self.bot.send_message(
                    chat_id=self.dump_channel_id,
                    text=processed_caption,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                
            logger.info(f"Forwarded {reason} message to dump: {message.message_id}")
        except Exception as e:
            logger.error(f"Error handling invalid message: {e}")

    def _store_hashes(self, message_id: int, media_hashes: List[Dict]):
        """Store media hashes with FIFO eviction policy"""
        while len(self.hash_data) >= MAX_HASH_ENTRIES and self.hash_data:
            oldest_id = min(self.hash_data.keys(), key=int)
            del self.hash_data[oldest_id]
        
        self.hash_data[str(message_id)] = media_hashes
        self._save_hash_data()

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
                image = Image.open(io.BytesIO(file_bytes))
                
                media_hashes.append({
                    'type': 'photo',
                    'phash': str(imagehash.phash(image)),
                    'sha256': hashlib.sha256(file_bytes).hexdigest(),
                    'file_id': largest_photo.file_id
                })
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
                    'file_id': video.file_id
                })
            except Exception as e:
                logger.error(f"Error processing video: {e}")
        
        return media_hashes

    async def _send_to_target(self, source_message: Message, media: Dict, caption: str):
        """Send single non-duplicate media to target channel"""
        try:
            target_channel = get_target_channel()
            if not target_channel:
                logger.error("No target channel configured!")
                return
                
            processor = Processor()
            processed_caption = await processor.process(caption or "")
            
            if media['type'] == 'photo':
                sent_message = await self.bot.send_photo(
                    chat_id=target_channel,
                    photo=media['file_id'],
                    caption=processed_caption,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            elif media['type'] == 'video':
                sent_message = await self.bot.send_video(
                    chat_id=target_channel,
                    video=media['file_id'],
                    caption=processed_caption,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            
            # Store the new message ID in our hash data
            if sent_message:
                self._store_hashes(sent_message.message_id, [media])
                
        except Exception as e:
            logger.error(f"Failed to send to target channel: {str(e)}")

    async def _send_group_to_target(self, source_message: Message, media_list: List[Dict]):
        """Send group of non-duplicate media to target channel"""
        try:
            target_channel = get_target_channel()
            if not target_channel:
                logger.error("No target channel configured!")
                return
                
            processor = Processor()
            processed_caption = await processor.process(source_message.caption or "")
            
            media_group = []
            for media in media_list:
                if media['type'] == 'photo':
                    media_group.append(InputMediaPhoto(
                        media=media['file_id'],
                        caption=processed_caption if len(media_group) == 0 else None,
                        parse_mode=ParseMode.MARKDOWN_V2
                    ))
                elif media['type'] == 'video':
                    media_group.append(InputMediaVideo(
                        media=media['file_id'],
                        caption=processed_caption if len(media_group) == 0 else None,
                        parse_mode=ParseMode.MARKDOWN_V2
                    ))
            
            if media_group:
                sent_messages = await self.bot.send_media_group(
                    chat_id=target_channel,
                    media=media_group
                )
                
                # Store the new message IDs in our hash data
                if sent_messages:
                    for msg, media in zip(sent_messages, media_list):
                        self._store_hashes(msg.message_id, [media])
                        
        except Exception as e:
            logger.error(f"Failed to send media group to target channel: {str(e)}")