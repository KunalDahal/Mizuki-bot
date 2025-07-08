import logging
from telethon.tl.types import MessageService
from telethon.errors import FloodWaitError
import asyncio

logger = logging.getLogger(__name__)

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
        valid_messages = [msg for msg in messages if not isinstance(msg, MessageService)]

        if not valid_messages:
            logger.debug("No valid messages in group")
            return []

        try:
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
                    wait_time = min(2 ** attempt, 60) 
                    await asyncio.sleep(wait_time)
        
        logger.error(f"Failed to forward after {max_retries} attempts")
        return None
