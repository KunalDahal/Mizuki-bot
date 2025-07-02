import logging
from typing import Dict, List
from telegram import Message, Update
from telegram.ext import MessageHandler, filters, ContextTypes
import os
from util import (
    load_banned_words,
    save_banned_words,
    HASH_FILE,
    MAX_HASH_ENTRIES,
    get_target_channel_id
)
import json
from PIL import Image
import imagehash
import hashlib
import io
import asyncio

logger = logging.getLogger(__name__)

class SardarMonitor:
    def __init__(self, application):
        self.application = application
        self.bot = application.bot
        self.current_caption = ""
        self.is_monitoring = False
        self.hash_data = {}
        self.banned_words = []
        self.target_channel_id = get_target_channel_id()
        self._load_hash_data()
        self._load_banned_words()
        self.message_queue = {}  # Track message processing order

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

    def _save_banned_words(self):
        """Save banned words to JSON file"""
        save_banned_words(self.banned_words)

    async def start(self):
        """Start monitoring the target channel for new messages"""
        if self.is_monitoring:
            logger.warning("Monitor is already running")
            return

        self.is_monitoring = True
        logger.info("Starting channel monitor...")

        # Register handler for new channel posts
        self.application.add_handler(
            MessageHandler(
                filters.Chat(self.target_channel_id) & 
                (filters.PHOTO | filters.VIDEO),
                self._process_message
            )
        )

    async def stop(self):
        """Stop monitoring the target channel"""
        self.is_monitoring = False
        logger.info("Stopping channel monitor...")

    async def _process_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process a new message from the target channel"""
        message = update.effective_message
        if not message:
            return

        try:
            # Store the caption first
            self.current_caption = message.caption or ""
            msg_id = message.message_id
            
            # Add to processing queue
            self.message_queue[msg_id] = {
                'caption': self.current_caption,
                'processed': False
            }

            # Check for banned words
            if self._contains_banned_words(self.current_caption):
                logger.info(f"Deleting message {msg_id} due to banned words")
                await message.delete()
                del self.message_queue[msg_id]
                return

            # Process media hashes
            media_hashes = await self._generate_media_hashes(message)
            duplicates = self._find_duplicates(media_hashes)

            if duplicates:
                await self._handle_duplicates(message, media_hashes, duplicates)
            else:
                # Only store if not duplicate and we have space
                if len(self.hash_data) < MAX_HASH_ENTRIES:
                    self._store_hashes(msg_id, media_hashes)
                    self.message_queue[msg_id]['processed'] = True
                else:
                    logger.warning(f"Hash storage full ({MAX_HASH_ENTRIES} entries), not storing new hashes")
        except Exception as e:
            logger.error(f"Error processing message {msg_id}: {e}")
        finally:
            # Clean up queue
            if msg_id in self.message_queue:
                self.message_queue[msg_id]['processed'] = True

    def _contains_banned_words(self, text: str) -> bool:
        """Check if text contains any banned words"""
        if not text or not self.banned_words:
            return False
        
        text_lower = text.lower()
        return any(banned_word.lower() in text_lower for banned_word in self.banned_words)

    async def _generate_media_hashes(self, message: Message) -> List[Dict]:
        """Generate hashes for all media in a message"""
        media_hashes = []
        
        # Handle photo
        if message.photo:
            try:
                largest_photo = message.photo[-1]  # Get highest resolution
                file = await largest_photo.get_file()
                
                # Skip if file is too large (over 50MB for photos)
                if file.file_size and file.file_size > 50_000_000:
                    logger.warning(f"Skipping large photo ({file.file_size/1_000_000:.1f}MB)")
                    return media_hashes
                    
                file_bytes = await file.download_as_bytearray()
                
                # Generate perceptual hash
                image = Image.open(io.BytesIO(file_bytes))
                phash = str(imagehash.phash(image))
                
                # Generate SHA256
                sha256 = hashlib.sha256(file_bytes).hexdigest()
                
                media_hashes.append({
                    'type': 'photo',
                    'phash': phash,
                    'sha256': sha256,
                    'file_id': largest_photo.file_id,
                    'caption': self.current_caption
                })
            except Exception as e:
                logger.error(f"Error processing photo: {e}")
                return media_hashes
        
        # Handle video
        elif message.video:
            try:
                video = message.video
                file = await video.get_file()
                
                # Calculate target size (10% of file size or 10MB max)
                target_size = min(
                    int(video.file_size * 0.1) if video.file_size else 10_000_000,
                    10_000_000  # Max 10MB
                )
                
                file_bytes = bytearray()
                async for chunk in file.download_as_bytearray(chunk_size=1_000_000):  # 1MB chunks
                    remaining = target_size - len(file_bytes)
                    if remaining <= 0:
                        break
                    file_bytes.extend(chunk[:remaining])
                
                # Generate SHA256 from partial content
                sha256 = hashlib.sha256(file_bytes).hexdigest()
                
                media_hashes.append({
                    'type': 'video',
                    'sha256': sha256,
                    'file_id': video.file_id,
                    'partial_size': len(file_bytes),
                    'caption': self.current_caption
                })
            except Exception as e:
                logger.error(f"Error processing video: {e}")
                return media_hashes
        
        return media_hashes

    def _find_duplicates(self, media_hashes: List[Dict]) -> Dict:
        """Find duplicates in the hash database"""
        duplicates = {}
        
        for media in media_hashes:
            for stored_id, stored_media_list in self.hash_data.items():
                for stored_media in stored_media_list:
                    # Only compare same media types
                    if stored_media['type'] != media['type']:
                        continue
                    
                    # Compare perceptual hash for photos
                    if media['type'] == 'photo' and 'phash' in media and 'phash' in stored_media:
                        if media['phash'] == stored_media['phash']:
                            if stored_id not in duplicates:
                                duplicates[stored_id] = []
                            duplicates[stored_id].append(stored_media)
                    
                    # Compare SHA256 for both photos and videos
                    if media['sha256'] == stored_media['sha256']:
                        if stored_id not in duplicates:
                            duplicates[stored_id] = []
                        duplicates[stored_id].append(stored_media)
        
        return duplicates
       
    # async def _handle_duplicates(self, message: Message, media_hashes: List[Dict], duplicates: Dict):
    #     try:
    #         current_id = message.message_id
    #         global_caption = None
    #         post_type = "group" if message.media_group_id else "single"
    #         for media in media_hashes:
    #             post_id = str(media.get("post_id"))
    #             if post_id:
    #                 if post_id in self.hash_data:
    #                     for entry in self.hash_data[post_id]:
    #                         entry["post_type"] = post_type
    #                 else:
    #                     self.hash_data[post_id] = [{
    #                         **media,
    #                         "post_type": post_type
    #                     }]
    #         self._save_hash_data()

    #         # 1. Collect caption before deleting
    #         collected_captions = []

    #         if len(media_hashes) == 1:
    #             if message.caption:
    #                 logger.info(f"Collected single media caption from message {current_id}")
    #                 collected_captions.append(message.caption)
    #         else:
    #             for media in media_hashes:
    #                 cap = media.get('caption')
    #                 if cap:
    #                     collected_captions.append(cap)

    #         if collected_captions:
    #             global_caption = "\n\n".join(collected_captions).strip()
    #             logger.info(f"Final caption collected:\n{global_caption}")
    #         else:
    #             logger.info("No captions found in any media.")

    #         # 2. Delete message after caption collected
    #         logger.info(f"Deleting duplicate message {current_id}")
    #         await message.delete()

    #         # 3. Mark duplicates
    #         for msg_id in duplicates:
    #             if str(msg_id) in self.hash_data:
    #                 for media in self.hash_data[str(msg_id)]:
    #                     media['is_duplicate'] = True

    #         self._save_hash_data()

    #         # 4. Remove from queue and hash
    #         if current_id in self.message_queue:
    #             del self.message_queue[current_id]

    #         for msg_id in duplicates:
    #             if str(msg_id) in self.hash_data:
    #                 del self.hash_data[str(msg_id)]

    #         self._save_hash_data()

    #         # ✅ 5. Check media_hashes directly for remaining valid media
    #         non_duplicate_media = [
    #             media for media in media_hashes
    #             if not media.get('is_duplicate') and media.get('file_id')
    #         ]

    #         # ✅ 6. Decide caption forwarding based on rules
    #         if post_type == "single":
    #             logger.info("Post is single. Skipping caption forward for duplicate.")
    #             return  # don't forward caption at all if single

    #         if post_type == "group":
    #             if not non_duplicate_media:
    #                 logger.info("Grouped post but all media are duplicate. Skipping caption forward.")
    #                 return  # don't forward caption if all grouped media are duplicate
    #             if global_caption:
    #                 logger.info("Forwarding caption because some valid group media remain.")
    #                 try:
    #                     await self.bot.send_message(
    #                         chat_id=self.target_channel_id,
    #                         text=global_caption,
    #                         parse_mode="HTML"
    #                     )
    #                 except Exception as e:
    #                     logger.error(f"Failed to send caption message: {e}")
    #             else:
    #                 logger.info("No caption to forward even though media remain.")

    #     except Exception as e:
    #         logger.error(f"Error in duplicate handling: {e}")

    async def _handle_duplicates(self, message: Message, media_hashes: List[Dict], duplicates: Dict):
        """Handle duplicate media by forcefully deleting new duplicates while keeping originals"""
        try:
            current_id = message.message_id
            is_group = bool(message.media_group_id)
            
            if not duplicates:
                logger.info(f"No duplicates found for message {current_id}")
                return

            # For single messages
            if not is_group:
                logger.info(f"Deleting new duplicate message {current_id}")
                try:
                    await message.delete()
                    # Double-check deletion
                    try:
                        msg = await self.bot.get_message(chat_id=message.chat.id, message_id=current_id)
                        logger.error(f"Message {current_id} still exists after deletion!")
                    except:
                        logger.info(f"Confirmed message {current_id} deleted")
                    return
                except Exception as e:
                    logger.error(f"Failed to delete message {current_id}: {e}")
                    # Try alternative deletion method
                    try:
                        await self.bot.delete_message(
                            chat_id=message.chat.id,
                            message_id=current_id
                        )
                        logger.info(f"Deleted via secondary method: {current_id}")
                    except Exception as e2:
                        logger.error(f"Complete failure deleting {current_id}: {e2}")
                    return

            # For media groups
            logger.info(f"Duplicate in group {current_id}, deleting entire group...")
            
            # Get all messages in this media group (including current message)
            messages_in_group = []
            try:
                if message.media_group_id:
                    # First try to delete the entire album at once
                    try:
                        await message.delete()
                        logger.info(f"Deleted media group {message.media_group_id} via album delete")
                        return
                    except:
                        pass
                    
                    # Fallback to individual message deletion
                    async for msg in self.bot.get_chat_history(
                        chat_id=message.chat.id,
                        limit=100
                    ):
                        if (msg.media_group_id == message.media_group_id and 
                            msg.message_id >= message.message_id - 10 and 
                            msg.message_id <= message.message_id + 10):
                            messages_in_group.append(msg.message_id)
            except Exception as e:
                logger.error(f"Error finding group messages: {e}")
                messages_in_group = [current_id]  # Fallback to just current message

            # Delete all found messages with retries
            deleted_count = 0
            for msg_id in messages_in_group:
                retries = 3
                while retries > 0:
                    try:
                        await self.bot.delete_message(
                            chat_id=message.chat.id,
                            message_id=msg_id
                        )
                        deleted_count += 1
                        logger.info(f"Deleted group message {msg_id}")
                        break
                    except Exception as e:
                        retries -= 1
                        if retries == 0:
                            logger.error(f"Failed to delete {msg_id} after 3 attempts: {e}")
                        else:
                            await asyncio.sleep(1)

            logger.info(f"Deleted {deleted_count}/{len(messages_in_group)} group messages")

            # Cleanup data regardless of deletion success
            for msg_id in messages_in_group:
                if str(msg_id) in self.hash_data:
                    del self.hash_data[str(msg_id)]
                if msg_id in self.message_queue:
                    del self.message_queue[msg_id]
            self._save_hash_data()

        except Exception as e:
            logger.error(f"Critical error in duplicate handling: {e}")
            # Emergency cleanup
            try:
                if str(current_id) in self.hash_data:
                    del self.hash_data[str(current_id)]
                    self._save_hash_data()
            except:
                pass

    def _store_hashes(self, message_id: int, media_hashes: List[Dict]):
        """Store media hashes in the database with entry limit"""
        try:
            if len(self.hash_data) >= MAX_HASH_ENTRIES:
                oldest_id = next(iter(self.hash_data))
                logger.info(f"Removing oldest hash entry {oldest_id} to make space")
                del self.hash_data[oldest_id]
            
            message_id_str = str(message_id)
            self.hash_data[message_id_str] = media_hashes
            self._save_hash_data()
        except Exception as e:
            logger.error(f"Error storing hashes for message {message_id}: {e}")