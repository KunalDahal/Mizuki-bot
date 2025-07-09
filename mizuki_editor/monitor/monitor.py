# monitor.py
import asyncio
import logging
import os
import time
import random
from collections import deque, defaultdict
from mizuki_editor.monitor.session import create_session
from util import get_bot_username, load_channels, save_channels, SOURCE_FILE
from telethon.errors import ChannelPrivateError, ChannelInvalidError, FloodWaitError
from mizuki_editor.monitor.recovery import RecoverySystem
from mizuki_editor.monitor.forward import Forwarder

logger = logging.getLogger(__name__)

class ChannelMonitor:
    def __init__(self):
        self.running = False
        self.client = create_session()
        self.bot_username = get_bot_username()
        self.channel_ids = load_channels()
        self.last_message_ids = {}
        self.access_errors = {}
        self.forward_attempts = {} 
        self.processing_semaphore = asyncio.Semaphore(3)
        self.base_delay = 2
        self.channel_check_jitter = (0, 10)
        self.queue_delay_jitter = (0, 10)
        self.last_channel_file_check = time.time()  # Initialize with current time
        self.channel_file_check_interval = 30  # Reduced from 300 to 30 seconds
        
        self.channel_backoffs = defaultdict(float)
        self.min_backoff = 5
        self.max_backoff = 3600
        self.backoff_factor = 1.5
        
        self.recovery = RecoverySystem()
        self.queue_lock = asyncio.Lock()
        self.message_queue = deque()

        asyncio.create_task(self.backoff_decay())

    async def backoff_decay(self):
        """Periodically reduce backoff times"""
        while self.running:
            await asyncio.sleep(3600)
            for channel_id in list(self.channel_backoffs):
                self.channel_backoffs[channel_id] *= 0.8
                if self.channel_backoffs[channel_id] < self.min_backoff:
                    del self.channel_backoffs[channel_id]

    async def run(self):
        self.running = True
        try:
            logging.getLogger("telethon.client.updates").setLevel(logging.WARNING)
            await self.client.connect()

            if not await self.client.is_user_authorized():
                logger.error("Session not authorized! Please run setup_session.py first.")
                await self.client.disconnect()
                return
                
            await self.client.start()
            logger.info("Telethon session started")

            # Initialize recovery for all channels
            await self.initialize_all_channels()

            # Start queue processor
            asyncio.create_task(self._process_queue())

            logger.info("Starting continuous channel monitoring with %d channels", len(self.channel_ids))
            while self.running:
                try:
                    await self._check_channel_file_updates()
                    await self.monitor_channels()
                    await asyncio.sleep(1)  # Small sleep between full cycles
                except Exception as e:
                    logger.error(f"Error in main monitoring loop: {e}", exc_info=True)
                    await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Monitor crashed: {e}", exc_info=True)
        finally:
            self.running = False
            try:
                await self.client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting client: {e}")

    async def initialize_all_channels(self):
        """Initialize all channels in the list"""
        for channel_id in self.channel_ids:
            try:
                await self.recovery.initialize_channel_state(self.client, channel_id)
                entity = await self.client.get_entity(channel_id)
                messages = await self.client.get_messages(entity, limit=1)
                if messages:
                    self.last_message_ids[channel_id] = messages[0].id
                    logger.info(f"Initialized channel {channel_id} with last ID: {messages[0].id}")
                else:
                    self.last_message_ids[channel_id] = 0
                    logger.info(f"Initialized channel {channel_id} with last ID: 0 (no messages)")
            except Exception as e:
                logger.error(f"Error initializing channel {channel_id}: {e}")
                self.last_message_ids[channel_id] = 0

    async def monitor_channels(self):
        """Monitor all channels for new messages"""
        valid_channels = []
        for channel_id in self.channel_ids:
            if self.access_errors.get(channel_id, 0) > 5:
                logger.warning(f"Skipping channel {channel_id} due to persistent errors")
                continue

            try:
                await self.check_channel(channel_id)
                self.access_errors[channel_id] = 0
                valid_channels.append(channel_id)
            except (ChannelPrivateError, ChannelInvalidError) as e:
                logger.error(f"No access to channel {channel_id}: {e}")
                self.access_errors[channel_id] = self.access_errors.get(channel_id, 0) + 1
            except FloodWaitError as e:
                logger.warning(f"Flood wait required for {channel_id}: {e.seconds} seconds")
                await asyncio.sleep(e.seconds + 5)
            except Exception as e:
                logger.error(f"Error checking channel {channel_id}: {e}")
                self.access_errors[channel_id] = self.access_errors.get(channel_id, 0) + 1

            await asyncio.sleep(random.uniform(*self.channel_check_jitter))

        if len(valid_channels) != len(self.channel_ids):
            self.channel_ids = valid_channels
            save_channels(self.channel_ids)
            logger.info("Updated channel list with %d valid channels", len(valid_channels))

    async def _check_channel_file_updates(self):
        """Check for updates to the channel source file and reload if needed"""
        current_time = time.time()
        if current_time - self.last_channel_file_check < self.channel_file_check_interval:
            return

        try:
            if not os.path.exists(SOURCE_FILE):
                logger.warning("Source file does not exist")
                return

            file_mtime = os.path.getmtime(SOURCE_FILE)
            if file_mtime > self.last_channel_file_check:
                logger.info("Detected changes in source file, reloading channels")
                new_channels = load_channels()
                added = set(new_channels) - set(self.channel_ids)
                removed = set(self.channel_ids) - set(new_channels)

                if added or removed:
                    logger.info(f"Channel changes detected. Added: {added}, Removed: {removed}")
                    self.channel_ids = new_channels
                    
                    for channel_id in added:
                        try:
                            entity = await self.client.get_entity(channel_id)
    
                            messages = await self.client.get_messages(
                                entity,
                                limit=1,
                                reverse=False
                            )
                            
                            if messages:
                                self.last_message_ids[channel_id] = messages[0].id
                                self.recovery.update_channel_state(channel_id, messages[0].id)
                                logger.info(f"Initialized NEW channel {channel_id} with CURRENT message ID: {messages[0].id} (will only monitor FUTURE messages)")
                            else:

                                self.last_message_ids[channel_id] = 0
                                self.recovery.update_channel_state(channel_id, 0)
                                logger.info(f"Initialized NEW channel {channel_id} with last ID: 0 (no messages yet)")
                        except Exception as e:
                            logger.error(f"Error initializing new channel {channel_id}: {e}")
                            self.last_message_ids[channel_id] = 0
                            self.recovery.update_channel_state(channel_id, 0)

                    for channel_id in removed:
                        if channel_id in self.last_message_ids:
                            del self.last_message_ids[channel_id]
                        if channel_id in self.access_errors:
                            del self.access_errors[channel_id]
                        if channel_id in self.recovery.last_message_ids:
                            del self.recovery.last_message_ids[channel_id]
                        logger.info(f"Removed channel {channel_id} from monitoring")

        except Exception as e:
            logger.error(f"Error checking channel file updates: {e}")
        finally:
            self.last_channel_file_check = current_time

    async def check_channel(self, channel_id):
        """Check a channel for new messages and add them to processing queue"""
        last_id = self.recovery.get_last_message_id(channel_id)
        try:
            entity = await self.client.get_entity(channel_id)
            
            async with self.queue_lock:
                queue_size = len(self.message_queue)
            max_messages = 5 if queue_size > 20 else 100
            
            messages = await self.client.get_messages(
                entity,
                limit=max_messages,
                min_id=last_id,
                reverse=True
            )
            
            if not messages:
                return
                
            new_messages = [msg for msg in messages if msg.id > last_id]
            
            if new_messages:
                logger.info(f"Found {len(new_messages)} new messages in channel {channel_id}")
                
                new_last_id = max(msg.id for msg in new_messages)
                self.recovery.update_channel_state(channel_id, new_last_id)
                
                grouped = {}
                single = []
                for msg in new_messages:
                    if msg.grouped_id:
                        grouped.setdefault(msg.grouped_id, []).append(msg)
                    else:
                        single.append(msg)
                
                async with self.queue_lock:
                    for group in grouped.values():
                        self.message_queue.append((channel_id, group))
                    
                    for i in range(0, len(single), 5):
                        batch = single[i:i+5]
                        self.message_queue.append((channel_id, batch))
                        
        except Exception as e:
            logger.error(f"Error checking channel {channel_id}: {e}")
            raise
            
    async def _process_queue(self):
        """Process messages from the queue with delays and backoffs"""
        logger.info("Queue processor started")
        while self.running:  
            async with self.queue_lock:
                if not self.message_queue:
                    await asyncio.sleep(1)
                    continue
                
                channel_id, messages = self.message_queue.popleft()
                
            current_time = time.time()
            backoff_end = self.channel_backoffs.get(channel_id, 0)
            if current_time < backoff_end:
                wait_time = backoff_end - current_time
                logger.info(f"Channel {channel_id} in backoff, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                async with self.queue_lock:
                    self.message_queue.appendleft((channel_id, messages))
                continue
                
            try:
                jitter = random.uniform(*self.queue_delay_jitter)
                total_delay = self.base_delay + jitter
                logger.debug(f"Waiting {total_delay:.2f}s before processing {len(messages)} messages from {channel_id}")
                await asyncio.sleep(total_delay)
                
                forwarder = Forwarder(self.client, self.bot_username)
                result = await forwarder.forward_with_retry(messages)
                
                if not result:
                    current_backoff = self.channel_backoffs.get(channel_id, self.min_backoff)
                    new_backoff = min(current_backoff * self.backoff_factor, self.max_backoff)
                    self.channel_backoffs[channel_id] = current_time + new_backoff
                    logger.warning(f"Set backoff for channel {channel_id}: {new_backoff:.1f}s")
                    
                    async with self.queue_lock:
                        self.message_queue.appendleft((channel_id, messages))
                else:
                    if messages:
                        last_id = max(m.id for m in messages)
                        self.recovery.update_channel_state(channel_id, last_id)
                
            except Exception as e:
                logger.error(f"Error processing queue item: {e}")
                async with self.queue_lock:
                    self.message_queue.appendleft((channel_id, messages))
                await asyncio.sleep(10)