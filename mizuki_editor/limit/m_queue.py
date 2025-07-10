import asyncio
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class MediaItem:
    message_id: int
    media: object 
    caption: Optional[str]
    grouped_id: Optional[int] = None
    formatting_entities: Optional[Any] = None  # Add this line

class ProcessingQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.processing_groups: Dict[int, List[MediaItem]] = defaultdict(list)
        self.lock = asyncio.Lock()

    async def add_to_queue(
        self, 
        message_id: int, 
        media: object, 
        caption: Optional[str], 
        grouped_id: Optional[int] = None,
        formatting_entities: Optional[Any] = None  # Add this parameter
    ):
        """Add a media item to the processing queue"""
        item = MediaItem(
            message_id=message_id,
            media=media,
            caption=caption,
            grouped_id=grouped_id,
            formatting_entities=formatting_entities  # Add this
        )
        
        async with self.lock:
            if grouped_id:
                self.processing_groups[grouped_id].append(item)
                # Only add to queue if this is the first item in the group
                if len(self.processing_groups[grouped_id]) == 1:
                    await self.queue.put((grouped_id, True))
            else:
                await self.queue.put((item, False))
        
        logger.info(f"📥 Added to queue - Message ID: {message_id}, Group: {grouped_id or 'None'}")

    async def get_next_item(self) -> Tuple[MediaItem | int, bool]:
        """Get the next media item to process (returns tuple of item and is_group flag)"""
        return await self.queue.get()

    async def get_group_items(self, group_id: int) -> List[MediaItem]:
        """Get all items for a group"""
        async with self.lock:
            items = self.processing_groups.pop(group_id, [])
            return items

    def task_done(self):
        """Mark the current task as done"""
        self.queue.task_done()