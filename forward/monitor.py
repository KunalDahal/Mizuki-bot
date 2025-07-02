import asyncio
import logging
from forward.session import create_session
from util import get_bot_username, load_channels, save_channels
from telethon.errors import ChannelPrivateError, ChannelInvalidError, FloodWaitError
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
        self.access_errors = {}
        self.jitter_range = (2, 10)
        self.forward_attempts = {}  # Track forwarding attempts per message

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

            # Initialize last message IDs
            for channel_id in self.channel_ids:
                try:
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

            logger.info("Starting continuous channel monitoring")
            while self.running:
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

    async def check_channel(self, channel_id):
        last_id = self.last_message_ids.get(channel_id, 0)
        try:
            entity = await self.client.get_entity(channel_id)
            messages = await self.client.get_messages(entity, min_id=last_id, limit=100)

            if messages:
                messages = sorted(messages, key=lambda m: m.id)
                grouped_messages = {}
                single_messages = []

                for msg in messages:
                    if isinstance(msg, MessageService):
                        continue

                    if msg.grouped_id:
                        grouped_messages.setdefault(msg.grouped_id, []).append(msg)
                    else:
                        single_messages.append(msg)

                # Process media groups with retry logic
                for group_id, group in grouped_messages.items():
                    group.sort(key=lambda m: m.id)
                    max_id = max(m.id for m in group)
                    
                    if max_id > last_id:
                        success = await self.forward_with_retry(
                            self.forward_message_group,
                            group,
                            f"media group {group_id} from {channel_id}"
                        )
                        if success:
                            self.last_message_ids[channel_id] = max_id

                # Process single messages with retry logic
                for msg in single_messages:
                    if msg.id > last_id:
                        success = await self.forward_with_retry(
                            self.forward_message,
                            msg,
                            f"message {msg.id} from {channel_id}"
                        )
                        if success:
                            self.last_message_ids[channel_id] = msg.id

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