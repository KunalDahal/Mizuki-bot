import asyncio
import logging
import time
from client.session import create_session
from util import get_bot_username, load_channels, save_channels
from telethon.errors import ChannelPrivateError, ChannelInvalidError
from telethon.types import MessageService
import random

logger = logging.getLogger(__name__)


class ChannelMonitor:
    def __init__(self):
        self.running = False
        self.client = create_session()
        self.bot_username = get_bot_username()
        self.channel_ids = load_channels()
        self.last_message_ids = {}
        self.last_forward_time = 0
        self.access_errors = {}
        self.min_interval = 15
        self.jitter_range = 5

    async def run(self):
        self.running = True
        try:
            logging.getLogger("telethon.client.updates").setLevel(logging.WARNING)
            await self.client.connect()

            # Check if session is authorized
            if not await self.client.is_user_authorized():
                logger.error(
                    "Session not authorized! Please run setup_session.py first."
                )
                await self.client.disconnect()
                return
            await self.client.start()
            logger.info("Telethon session started")

            # Initialize last message IDs
            for channel_id in self.channel_ids:
                try:
                    entity = await self.client.get_entity(channel_id)
                    messages = await self.client.get_messages(entity, limit=1)
                    if messages:
                        self.last_message_ids[channel_id] = messages[0].id
                        logger.info(
                            f"Initialized channel {channel_id} with last ID: {messages[0].id}"
                        )
                    else:
                        self.last_message_ids[channel_id] = 0
                except Exception as e:
                    logger.error(f"Error initializing channel {channel_id}: {e}")
                    self.last_message_ids[channel_id] = 0

            logger.info("Starting channel monitoring")
            try:
                while True:
                    start_time = time.time()
                    valid_channels = []

                    for channel_id in self.channel_ids:
                        # Skip channels with persistent errors
                        if self.access_errors.get(channel_id, 0) > 5:
                            logger.warning(
                                f"Skipping channel {channel_id} due to persistent errors"
                            )
                            continue

                        try:
                            await self.check_channel(channel_id)
                            self.access_errors[channel_id] = 0  # Reset error count
                            valid_channels.append(channel_id)
                        except (ChannelPrivateError, ChannelInvalidError) as e:
                            logger.error(f"No access to channel {channel_id}: {e}")
                            self.access_errors[channel_id] = (
                                self.access_errors.get(channel_id, 0) + 1
                            )
                        except Exception as e:
                            logger.error(f"Error checking channel {channel_id}: {e}")
                            self.access_errors[channel_id] = (
                                self.access_errors.get(channel_id, 0) + 1
                            )

                        await asyncio.sleep(10)  # 10-second gap between channels

                    # Update channel list (remove inaccessible channels)
                    if len(valid_channels) != len(self.channel_ids):
                        self.channel_ids = valid_channels
                        save_channels(self.channel_ids)

                    # Calculate remaining time for 60-second cycle
                    elapsed = time.time() - start_time
                    await asyncio.sleep(max(0, 60 - elapsed))

            except asyncio.CancelledError:
                logger.info("Monitoring stopped")
                self.running = False        
        except Exception as e:
            logger.error(f"Monitor crashed: {e}")
            self.running = False
        finally:
            self.running = False
            await self.client.disconnect()

    def is_running(self):
        return self.running

    async def check_channel(self, channel_id):
        last_id = self.last_message_ids.get(channel_id, 0)
        try:
            entity = await self.client.get_entity(channel_id)
            messages = await self.client.get_messages(entity, min_id=last_id, limit=100)

            if messages:
                # Sort messages by ID to ensure proper ordering
                messages = sorted(messages, key=lambda m: m.id)

                # Group messages by media group
                grouped_messages = {}
                single_messages = []

                for msg in messages:
                    # Skip service messages (pins, etc.)
                    if isinstance(msg, MessageService):
                        continue

                    if msg.grouped_id:
                        grouped_messages.setdefault(msg.grouped_id, []).append(msg)
                    else:
                        single_messages.append(msg)

                # Process media groups first
                for group_id, group in grouped_messages.items():
                    # Sort by message ID to maintain order
                    group.sort(key=lambda m: m.id)

                    try:
                        # Forward entire group
                        await self.forward_message_group(group)
                        max_id = max(m.id for m in group)
                        if max_id > last_id:
                            self.last_message_ids[channel_id] = max_id
                            logger.info(
                                f"New media group from {channel_id} (Max ID: {max_id})"
                            )
                    except Exception as e:
                        logger.error(f"Failed to forward media group {group_id}: {e}")
                        # Don't update last_message_id if forwarding failed

                # Process single messages
                for msg in single_messages:
                    if msg.id > last_id:
                        try:
                            await self.forward_message(msg)
                            self.last_message_ids[channel_id] = msg.id
                            logger.info(f"New message from {channel_id} (ID: {msg.id})")
                        except Exception as e:
                            logger.error(f"Failed to forward message {msg.id}: {e}")
                            # Don't update last_message_id if forwarding failed

                # Update to the highest message ID we've seen, regardless of forwarding success
                if messages:
                    highest_id = max(m.id for m in messages)
                    if highest_id > last_id:
                        self.last_message_ids[channel_id] = highest_id

        except Exception as e:
            logger.error(f"Error checking channel {channel_id}: {e}")
            raise
            
    async def forward_message(self, message):
        now = time.time()
        wait_time = max(0, self.min_interval - (now - self.last_forward_time))
        jitter = random.uniform(-self.jitter_range, self.jitter_range)
        total_wait = max(0, wait_time + jitter)

        if total_wait > 0:
            await asyncio.sleep(total_wait)

        try:
            await self.client.forward_messages(self.bot_username, message)
            self.last_forward_time = time.time()
        except Exception as e:
            logger.error(f"Forward failed: {e}")

    async def forward_message_group(self, messages):
        now = time.time()
        wait_time = max(0, self.min_interval - (now - self.last_forward_time))
        jitter = random.uniform(-self.jitter_range, self.jitter_range)
        total_wait = max(0, wait_time + jitter)

        if total_wait > 0:
            await asyncio.sleep(total_wait)

        try:
            await self.client.forward_messages(self.bot_username, messages)
            self.last_forward_time = time.time()
            logger.info(f"Forwarded media group ({len(messages)} items)")
        except Exception as e:
            logger.error(f"Group forward failed: {e}")
