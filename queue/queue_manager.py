import json
import os
import logging
from collections import deque
from typing import List, Dict, Any

logger = logging.getLogger(__name__)
QUEUE_FILE = 'queue.json'

class QueueManager:
    def __init__(self):
        self.queue = deque()
        self._load_queue()

    def _load_queue(self):
        if os.path.exists(QUEUE_FILE):
            try:
                with open(QUEUE_FILE, 'r') as f:
                    data = json.load(f)
                    self.queue = deque(data)
                logger.info(f"Loaded queue with {len(self.queue)} items")
            except Exception as e:
                logger.error(f"Error loading queue: {e}")
                self.queue = deque()

    def _save_queue(self):
        try:
            with open(QUEUE_FILE, 'w') as f:
                json.dump(list(self.queue), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving queue: {e}")

    def add_item(self, item: Dict[str, Any]):
        """Add an item to the queue"""
        self.queue.append(item)
        self._save_queue()
        logger.info(f"Added item to queue. Queue size: {len(self.queue)}")

    def get_next_item(self) -> Dict[str, Any]:
        """Get next item without removing it"""
        if self.queue:
            return self.queue[0]
        return None

    def remove_item(self):
        """Remove the first item from the queue"""
        if self.queue:
            self.queue.popleft()
            self._save_queue()

    def get_queue_size(self) -> int:
        return len(self.queue)

    def clear_queue(self):
        self.queue.clear()
        self._save_queue()
        logger.warning("Queue cleared")