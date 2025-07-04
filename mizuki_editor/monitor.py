import asyncio
import logging
import os
import time
from collections import deque
from mizuki_editor.session import create_session
from util import get_bot_username, load_channels, save_channels, SOURCE_FILE
from telethon.errors import ChannelPrivateError, ChannelInvalidError, FloodWaitError
import random
from mizuki_editor.recovery import RecoverySystem
from mizuki_editor.forward import Forwarder


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
        self.processing_semaphore = asyncio.Semaphore(1) 
        self.base_delay = 30 
        self.jitter_range = (0, 10)
        self.last_channel_file_check = 0
        self.channel_file_check_interval = 10  # Check every 5 minutes
        
        # Initialize missing attributes
        self.recovery = RecoverySystem()  # Add recovery system
        self.queue_lock = asyncio.Lock()  # Add queue lock
        self.message_queue = deque()  # Add message queue

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
                except Exception as e:
                    logger.error(f"Error initializing channel {channel_id}: {e}")
                    self.last_message_ids[channel_id] = 0

            # Start queue processor
            asyncio.create_task(self._process_queue())

            logger.info("Starting continuous channel monitoring")
            while self.running:
                # Check for channel file updates periodically
                await self._check_channel_file_updates()

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

                    # Random jitter between channel checks
                    await asyncio.sleep(random.uniform(*self.jitter_range))

                if len(valid_channels) != len(self.channel_ids):
                    self.channel_ids = valid_channels
                    save_channels(self.channel_ids)

        except Exception as e:
            logger.error(f"Monitor crashed: {e}")
        finally:
            self.running = False
            await self.client.disconnect()

    async def _check_channel_file_updates(self):
        """Check if the channel file has been modified and reload if needed"""
        current_time = time.time()
        if current_time - self.last_channel_file_check < self.channel_file_check_interval:
            return

        try:
            file_path = SOURCE_FILE
            if not os.path.exists(file_path):
                return

            file_mtime = os.path.getmtime(file_path)
            if file_mtime > self.last_channel_file_check:
                new_channels = load_channels()
                added = set(new_channels) - set(self.channel_ids)
                removed = set(self.channel_ids) - set(new_channels)

                if added or removed:
                    logger.info(f"Channel list updated. Added: {added}, Removed: {removed}")
                    self.channel_ids = new_channels
                    
                    # Initialize new channels
                    for channel_id in added:
                        try:
                            await self.recovery.initialize_channel_state(self.client, channel_id)
                            entity = await self.client.get_entity(channel_id)
                            messages = await self.client.get_messages(entity, limit=1)
                            if messages:
                                self.last_message_ids[channel_id] = messages[0].id
                                logger.info(f"Initialized new channel {channel_id} with last ID: {messages[0].id}")
                            else:
                                self.last_message_ids[channel_id] = 0
                        except Exception as e:
                            logger.error(f"Error initializing new channel {channel_id}: {e}")
                            self.last_message_ids[channel_id] = 0

                    # Clean up state for removed channels
                    for channel_id in removed:
                        if channel_id in self.last_message_ids:
                            del self.last_message_ids[channel_id]
                        if channel_id in self.access_errors:
                            del self.access_errors[channel_id]
                        if channel_id in self.recovery.last_message_ids:
                            del self.recovery.last_message_ids[channel_id]

        except Exception as e:
            logger.error(f"Error checking channel file updates: {e}")
        finally:
            self.last_channel_file_check = current_time
        
    async def check_channel(self, channel_id):
        """Check a channel for new messages and add them to processing queue"""
        last_id = self.recovery.get_last_message_id(channel_id)
        try:
            entity = await self.client.get_entity(channel_id)
            
            # Get messages newer than last_id
            messages = await self.client.get_messages(
                entity,
                limit=100,
                min_id=last_id,
                reverse=True  # Get newest messages first
            )
            
            # Filter to only messages newer than last_id (redundant but safe)
            new_messages = [msg for msg in messages if msg.id > last_id]
            
            if new_messages:
                logger.info(f"Found {len(new_messages)} new messages in channel {channel_id}")
                
                # Update last message ID immediately to prevent duplicates
                new_last_id = max(msg.id for msg in new_messages)
                self.recovery.update_channel_state(channel_id, new_last_id)
                
                # Group messages by media group or single
                grouped = {}
                single = []
                for msg in new_messages:
                    if msg.grouped_id:
                        grouped.setdefault(msg.grouped_id, []).append(msg)
                    else:
                        single.append(msg)
                
                # Add to queue
                async with self.queue_lock:
                    # Add media groups
                    for group in grouped.values():
                        self.message_queue.append((channel_id, group))
                    
                    # Add single messages in batches of 5
                    for i in range(0, len(single), 5):
                        batch = single[i:i+5]
                        self.message_queue.append((channel_id, batch))
                        
        except Exception as e:
            logger.error(f"Error checking channel {channel_id}: {e}")
            raise
            
    async def forward_with_retry(self, forward_func, messages, description):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await forward_func(messages)
                logger.info(f"Successfully forwarded {description}")
                return True
            except FloodWaitError as e:
                wait_time = e.seconds + random.uniform(1, 5)
                logger.warning(f"Flood wait for {description}, attempt {attempt + 1}/{max_retries}. Waiting {wait_time} seconds")
                await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"Failed to forward {description}, attempt {attempt + 1}/{max_retries}: {e}")
                await asyncio.sleep(random.uniform(*self.jitter_range))
        
        logger.error(f"Failed to forward {description} after {max_retries} attempts")
        return False

    async def forward_message(self, message):
        jitter = random.uniform(*self.jitter_range)
        await asyncio.sleep(jitter)
        await self.client.forward_messages(self.bot_username, message)

    async def forward_message_group(self, messages):
        jitter = random.uniform(*self.jitter_range)
        await asyncio.sleep(jitter)
        await self.client.forward_messages(self.bot_username, messages)
    
    async def _forward_messages(self, channel_id, messages):
        try:
            logger.info(f"Attempting to forward {len(messages)} messages from {channel_id}")
            if len(messages) > 1:
                await self.forward_message_group(messages)
            else:
                await self.forward_message(messages[0])
            
            if messages:
                last_id = max(m.id for m in messages)
                logger.info(f"Updating recovery state for {channel_id} to {last_id}")
                self.recovery.update_channel_state(channel_id, last_id)
                
        except Exception as e:
            logger.error(f"Error forwarding messages: {e}")
            raise
    
    async def _process_queue(self):
        """Process messages from the queue with delays"""
        while self.running:  # Add running check
            async with self.queue_lock:
                if not self.message_queue:
                    await asyncio.sleep(1)
                    continue
                
                channel_id, messages = self.message_queue.popleft()
                
            try:
                # Calculate delay with jitter
                jitter = random.uniform(*self.jitter_range)
                await asyncio.sleep(self.base_delay + jitter)
                
                # Use Forwarder class for consistent forwarding
                forwarder = Forwarder(self.client, self.bot_username)
                result = await forwarder.forward_with_retry(messages)
                
                if not result:
                    # Re-add to queue if failed
                    async with self.queue_lock:
                        self.message_queue.appendleft((channel_id, messages))
                        await asyncio.sleep(60)  # Wait longer before retry
                
            except Exception as e:
                logger.error(f"Error processing queue item: {e}")
                # Re-add to queue if error occurs
                async with self.queue_lock:
                    self.message_queue.appendleft((channel_id, messages))
                    await asyncio.sleep(60)  # Wait longer before retry