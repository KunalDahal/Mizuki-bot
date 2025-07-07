import asyncio
import logging
from queue_manager import QueueManager
from content_checker import ContentChecker
from telegram import Bot, Message
from mizuki_editor.forward import forward_to_all_targets

logger = logging.getLogger(__name__)

class QueueProcessor:
    def __init__(self, bot):
        self.bot = bot
        self.queue_manager = QueueManager()
        self.content_checker = ContentChecker()
        self.processing = False

    async def start(self):
        """Start processing queue continuously"""
        logger.info("Starting queue processor")
        while True:
            try:
                if not self.processing:
                    await self.process_next_item()
                await asyncio.sleep(5)  # Check queue every 5 seconds
            except Exception as e:
                logger.error(f"Queue processor error: {e}")

    async def process_next_item(self):
        """Process the next item in the queue"""
        item = self.queue_manager.get_next_item()
        if not item:
            return
            
        self.processing = True
        try:
            if item['type'] == 'single':
                await self._process_single(item)
            else:
                await self._process_group(item)
                
            # Only remove if processing succeeded
            self.queue_manager.remove_item()
        except Exception as e:
            logger.error(f"Failed to process queue item: {e}")
        finally:
            self.processing = False

    async def _process_single(self, item: Dict[str, Any]):
        """Process a single message item"""
        message = self._deserialize_message(item['message'])
        result = await self.content_checker._process_single_message(message)
        await self._handle_processing_result(result)

    async def _process_group(self, item: Dict[str, Any]):
        """Process a media group item"""
        messages = [self._deserialize_message(m) for m in item['messages']]
        result = await self.content_checker._process_complete_media_group(messages)
        await self._handle_processing_result(result)

    async def _handle_processing_result(self, result):
        """Handle the result of processing"""
        if isinstance(result, str):  # Text message
            await forward_to_all_targets(self.bot, text=result)
        elif isinstance(result, list):  # Media message
            await forward_to_all_targets(self.bot, media=result)

    def _deserialize_message(self, data: Dict[str, Any]) -> Message:
        """Recreate Message object from serialized data"""
        # Simplified deserialization - in practice you'd need to recreate
        # a proper Message object using the bot instance
        return Message(
            message_id=data['message_id'],
            chat_id=data['chat_id'],
            date=data['date'],
            text=data['text'],
            caption=data['caption'],
            # ... other attributes ...
        )