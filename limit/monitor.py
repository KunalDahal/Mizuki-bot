# monitor.py
import os
import hashlib
import asyncio
import logging
import json
import tempfile
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.network import ConnectionTcpFull
from limit.config import get_session_string_1, get_api_hash_1, get_api_id_1, get_source_id, get_target_id, VIDEO_HASH_FILE, JSON_FOLDER
from limit.m_queue import ProcessingQueue
from limit.content_checker import ContentChecker

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
telethon_logger = logging.getLogger('telethon')
telethon_logger.setLevel(logging.WARNING)

# Constants
CHUNK_SIZE = 5 * 1024 * 1024  # 5MB chunks for downloads
HASH_CHUNK_SIZE = 65536  # 64KB chunks for hashing
MAX_RETRIES = 3
RETRY_DELAY = 2
DOWNLOAD_TIMEOUT = 300  # 5 minutes

class VideoMonitor:
    def __init__(self):
        self.client = TelegramClient(
            session=StringSession(get_session_string_1()),
            api_id=get_api_id_1(),
            api_hash=get_api_hash_1(),
            connection=ConnectionTcpFull,
            connection_retries=5,
            auto_reconnect=True,
            request_retries=3,
            flood_sleep_threshold=60,
            base_logger=telethon_logger
        )
        self.source_channel = get_source_id()
        self.target_channel = get_target_id()
        self.queue = ProcessingQueue()
        self.content_checker = ContentChecker()
        self.processing_lock = asyncio.Lock()
        self.active_downloads = set()
        logger.info(f"🔄 Monitor initialized for source: {self.source_channel}, target: {self.target_channel}")

    async def calculate_file_hash(self, file_path):
        """Calculate SHA256 hash with progress tracking"""
        sha256_hash = hashlib.sha256()
        try:
            file_size = os.path.getsize(file_path)
            processed = 0
            start_time = datetime.now()
            
            logger.info(f"🔍 Starting hashing: {os.path.basename(file_path)} ({file_size/1024/1024:.2f}MB)")

            with open(file_path, "rb") as f:
                while chunk := f.read(HASH_CHUNK_SIZE):
                    sha256_hash.update(chunk)
                    processed += len(chunk)
                    progress = (processed / file_size) * 100
                    elapsed = (datetime.now() - start_time).total_seconds()
                    speed = (processed / 1024 / 1024) / max(elapsed, 0.1)
                    
                    if int(progress) % 25 == 0 or processed == file_size:
                        logger.info(
                            f"🔢 Hashing: {progress:.1f}% | "
                            f"{processed/1024/1024:.2f}/{file_size/1024/1024:.2f}MB | "
                            f"{speed:.2f}MB/s"
                        )

            file_hash = sha256_hash.hexdigest()
            logger.info(f"✅ Hash complete: {file_hash}")
            return file_hash
            
        except Exception as e:
            logger.error(f"❌ Hashing failed: {e}")
            return None

    async def download_with_retry(self, media, temp_path):
        """Download media with retry logic and detailed progress"""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if temp_path in self.active_downloads:
                    logger.warning(f"⚠️ Download already in progress for {temp_path}")
                    return False
                
                self.active_downloads.add(temp_path)
                file_size = getattr(media.document, 'size', 0) if hasattr(media, 'document') else 0
                
                logger.info(f"🚀 Download attempt {attempt}/{MAX_RETRIES}")
                logger.info(f"📦 Size: {file_size/1024/1024:.2f}MB | Chunk: {CHUNK_SIZE/1024/1024:.2f}MB")

                with open(temp_path, 'wb') as f:
                    downloaded = 0
                    start_time = datetime.now()
                    last_log_time = start_time
                    
                    async for chunk in self.client.iter_download(media, chunk_size=CHUNK_SIZE):
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        current_time = datetime.now()
                        if (current_time - last_log_time).total_seconds() >= 1 or downloaded == file_size:
                            elapsed = (current_time - start_time).total_seconds()
                            progress = (downloaded / file_size) * 100 if file_size > 0 else 0
                            speed = (downloaded / 1024 / 1024) / max(elapsed, 0.1)
                            remaining = (file_size - downloaded) / (downloaded / elapsed) if downloaded > 0 else 0
                            
                            logger.info(
                                f"⏳ Download: {progress:.1f}% | "
                                f"{downloaded/1024/1024:.2f}/{file_size/1024/1024:.2f}MB | "
                                f"{speed:.2f}MB/s | ETA: {remaining:.0f}s"
                            )
                            last_log_time = current_time

                if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    logger.info(f"✅ Download succeeded in {elapsed:.2f}s")
                    return True
                
                logger.warning(f"⚠️ Empty file after download (attempt {attempt})")

            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Timeout during download (attempt {attempt})")
            except Exception as e:
                logger.error(f"❌ Download error (attempt {attempt}): {e}")
            finally:
                self.active_downloads.discard(temp_path)

            if attempt < MAX_RETRIES:
                wait_time = RETRY_DELAY * attempt
                logger.info(f"🔄 Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)

        logger.error(f"🚨 Failed after {MAX_RETRIES} attempts")
        return False

    def get_file_extension(self, media):
        """Get appropriate file extension for the media"""
        if hasattr(media, 'document'):
            for attr in media.document.attributes:
                if hasattr(attr, 'file_name'):
                    return os.path.splitext(attr.file_name)[1]
            return '.mp4'  # Default extension for videos
        return '.jpg'  # Default extension for photos

    async def process_single_media(self, media_item, group_caption=None):
        """Full media processing pipeline with validation"""
        temp_path = None
        try:
            # Setup temp file with proper extension
            ext = self.get_file_extension(media_item.media)
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
                temp_path = temp_file.name
            logger.info(f"🛠️ Processing media to: {temp_path}")

            # Download phase
            if not await self.download_with_retry(media_item.media, temp_path):
                logger.error("❌ All download attempts failed")
                return None

            # Validate download
            if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                logger.error("❌ Downloaded file is invalid")
                return None

            # Hashing phase
            file_hash = await self.calculate_file_hash(temp_path)
            if not file_hash:
                logger.error("❌ Failed to generate file hash")
                return None

            # Duplicate check
            if self.content_checker.is_duplicate(file_hash):
                logger.warning(f"♻️ Duplicate detected! Hash: {file_hash}")
                return None

            # Use group caption if available, otherwise use individual caption
            caption = group_caption if group_caption else media_item.caption

            # Forwarding phase
            logger.info("📤 Forwarding to target channel...")
            forwarded = await self.client.send_file(
                self.target_channel,
                file=temp_path,
                caption=caption,
                supports_streaming=True,
                attributes=media_item.media.document.attributes if hasattr(media_item.media, 'document') else None
            )

            # Update records
            metadata = {
                'date': datetime.now().isoformat(),
                'caption': caption,
                'message_id': forwarded.id,
                'source_msg_id': media_item.message_id,
                'file_size': os.path.getsize(temp_path),
                'hash': file_hash
            }
            self.content_checker.add_hash(file_hash, metadata)
            self.content_checker.mark_message_processed(media_item.message_id)

            logger.info(f"🎉 Success! Forwarded as message {forwarded.id}")
            return forwarded

        except Exception as e:
            logger.error(f"🔥 Critical error: {e}")
            return None
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    logger.info(f"🧹 Cleaned temp file: {temp_path}")
                except Exception as e:
                    logger.error(f"⚠️ Failed to clean temp file: {e}")

    async def process_group_media(self, group_id):
        """Process all media items in a group"""
        async with self.processing_lock:
            group_items = await self.queue.get_group_items(group_id)
            if not group_items:
                return

            logger.info(f"👥 Processing group {group_id} with {len(group_items)} items")
            
            # Get the first valid caption from the group
            group_caption = None
            for item in group_items:
                if item.caption:
                    group_caption = item.caption
                    break
            
            # Process all items in the group
            for item in group_items:
                if not self.content_checker.is_message_processed(item.message_id):
                    await self.process_single_media(item, group_caption)

    async def process_queue(self):
        """Process items from the queue"""
        while True:
            try:
                item, is_group = await self.queue.get_next_item()
                
                if is_group:
                    await self.process_group_media(item)
                else:
                    if not self.content_checker.is_message_processed(item.message_id):
                        await self.process_single_media(item)
                
                self.queue.task_done()
                
            except Exception as e:
                logger.error(f"❌ Queue processing error: {e}")
                await asyncio.sleep(5)  # Prevent tight loop on errors

    async def process_message(self, message):
        """Process incoming message"""
        try:
            if self.content_checker.is_message_processed(message.id):
                logger.info(f"⏩ Skipping already processed message: {message.id}")
                return

            logger.info(f"📩 New message: {message.id}")
            
            if not message.media:
                if message.text:
                    await self.client.send_message(self.target_channel, message.text)
                    logger.info(f"📝 Forwarded text message: {message.id}")
                    self.content_checker.mark_message_processed(message.id)
                return

            # Handle caption properly for different message types
            caption = None
            if hasattr(message, 'text') and message.text:
                caption = message.text
            elif hasattr(message, 'caption'):
                caption = message.caption
            
            if hasattr(message, 'grouped_id') and message.grouped_id:
                await self.queue.add_to_queue(
                    message_id=message.id,
                    media=message.media,
                    caption=caption,
                    grouped_id=message.grouped_id
                )
                logger.info(f"👥 Added grouped media (ID: {message.grouped_id}) to queue")
            else:
                await self.queue.add_to_queue(
                    message_id=message.id,
                    media=message.media,
                    caption=caption
                )
                logger.info("📥 Added single media to queue")

        except Exception as e:
            logger.error(f"❌ Message processing failed: {e}")

    async def start(self):
        """Start monitoring the channel and processing queue"""
        @self.client.on(events.NewMessage(chats=self.source_channel))
        async def handler(event):
            try:
                await self.process_message(event.message)
            except Exception as e:
                logger.error(f"⚠️ Handler error: {e}")

        # Start the queue processor
        asyncio.create_task(self.process_queue())

        logger.info("🚀 Starting monitor...")
        await self.client.start()
        logger.info("✅ Monitor running")
        await self.client.run_until_disconnected()