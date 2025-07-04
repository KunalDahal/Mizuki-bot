import logging
from typing import Dict, List
from telegram import Message, Update,InputMediaVideo,InputMediaPhoto
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
        """Process incoming messages from source channels, detect duplicates, and forward accordingly."""
        message = update.effective_message
        if not message:
            return

        async with self.processing_semaphore:
            try:
                # Generate hashes for all media in this message
                media_hashes = await self._generate_media_hashes(message)
                logger.debug(f"Generated hashes: {media_hashes}")

                if not media_hashes:
                    return  # No valid media, nothing to do
                
                # Find which media are duplicates (indices)
                duplicate_indices = self._find_duplicate_indices(media_hashes)
                logger.debug(f"Duplicate indices: {duplicate_indices}")

                # Split into duplicates and non-duplicates directly from hashes
                duplicate_media = [media for i, media in enumerate(media_hashes) if i in duplicate_indices]
                non_duplicate_media = [media for i, media in enumerate(media_hashes) if i not in duplicate_indices]

                logger.debug(f"Found {len(duplicate_media)} duplicates, {len(non_duplicate_media)} non-duplicates")

                # If it's a single media message
                if len(media_hashes) == 1:
                    if duplicate_media:
                        await self._handle_invalid(message, "duplicate")
                    else:
                        self._store_hashes(message.message_id, media_hashes)
                    return

                # If it's a media group (multiple media)
                if not non_duplicate_media:
                    await self._handle_invalid(message, "duplicate")
                    return

                # Forward duplicate items to dump channel
                if duplicate_media:
                    await self._forward_duplicates(message, duplicate_indices, message.caption or "")

                # Process caption
                caption = message.caption or ""
                processor = Processor()
                processed_caption = await processor.process(caption)

                # Send only non-duplicate media to target channel
                if len(non_duplicate_media) == 1:
                    await self._send_to_target(non_duplicate_media[0], processed_caption)
                else:
                    await self._send_group_to_target(non_duplicate_media)

                # Store hashes of only non-duplicate media
                self._store_hashes(message.message_id, non_duplicate_media)

            except Exception as e:
                logger.error(f"Error processing message {getattr(message, 'message_id', 'unknown')}: {e}")



    async def _handle_invalid(self, message: Message, reason: str):
        """Forward invalid message to dump channel with processed text"""
        try:
            # Process the caption/text before forwarding
            caption = message.caption or message.text or ""
            processor = Processor()  # Create processor instance
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

    
    def _find_duplicate_indices(self, media_hashes: List[Dict]) -> List[int]:
        
        """Check for duplicate media and return indices of duplicates"""
        duplicate_indices = []
        
        for i, media in enumerate(media_hashes):
            for stored_media_list in self.hash_data.values():
                for stored_media in stored_media_list:
                    if stored_media['type'] != media['type']:
                        continue
                    
                    # Exact match for videos
                    if media['type'] == 'video' and media['sha256'] == stored_media['sha256']:
                        duplicate_indices.append(i)
                        break
                    
                    # Photo comparison
                    if media['type'] == 'photo':
                        if media['sha256'] == stored_media['sha256']:
                            duplicate_indices.append(i)
                            break
                        try:
                            h1 = imagehash.hex_to_hash(media['phash'])
                            h2 = imagehash.hex_to_hash(stored_media['phash'])
                            if h1 - h2 < 5:  # Fuzzy match
                                duplicate_indices.append(i)
                                break
                        except Exception as e:
                            logger.error(f"Error comparing image hashes: {e}")
        
        return duplicate_indices

    async def _forward_duplicates(self, message: Message, duplicate_indices: List[int], caption: str):
        """Forward duplicate media to dump channel"""
        try:
            if message.photo:
                # For photo messages, we can only forward the entire message
                await self._handle_invalid(message, "partial duplicate")
            elif message.video:
                # For video messages (in media groups), we can forward specific ones
                media_group = message.media_group
                if media_group:
                    for i in duplicate_indices:
                        media = media_group[i]
                        if media.type == 'video':
                            await self.bot.send_video(
                                chat_id=self.dump_channel_id,
                                video=media.file_id,
                                caption=caption,
                                parse_mode=ParseMode.MARKDOWN_V2
                            )
        except Exception as e:
            logger.error(f"Error forwarding duplicates: {e}")
            
    
    async def _send_to_target(self, media: Dict, caption: str):
        """Send single non-duplicate media to target channel"""
        target_channel = get_target_channel()
        try:
            if media['type'] == 'photo':
                await self.bot.send_photo(
                    chat_id=target_channel,
                    photo=media['file_id'],
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            elif media['type'] == 'video':
                await self.bot.send_video(
                    chat_id=target_channel,
                    video=media['file_id'],
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
        except Exception as e:
            logger.error(f"Error sending to target channel: {e}")

    async def _send_group_to_target(self, media_list: List[Dict]):
        """Send group of non-duplicate media to target channel"""
        target_channel = get_target_channel()
        try:
            # Telegram API requires sending media groups as a single operation
            media_group = []
            for i, media in enumerate(media_list):
                if media['type'] == 'photo':
                    media_group.append(InputMediaPhoto(media['file_id']))
                elif media['type'] == 'video':
                    media_group.append(InputMediaVideo(media['file_id']))
            
            await self.bot.send_media_group(
                chat_id=target_channel,
                media=media_group
            )
        except Exception as e:
            logger.error(f"Error sending media group to target channel: {e}")