import json
import os
from typing import Dict, Optional, Set
from mizuki_editor.limit.config import VIDEO_HASH_FILE
import logging

logger = logging.getLogger(__name__)

class ContentChecker:
    def __init__(self):
        self.video_hashes = self._load_hashes()
        self.seen_message_ids = set()

    def _load_hashes(self) -> Dict[str, dict]:
        """Load video hashes from file"""
        try:
            if os.path.exists(VIDEO_HASH_FILE):
                with open(VIDEO_HASH_FILE, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error loading video hashes: {e}")
            return {}

    def is_duplicate(self, file_hash: str) -> bool:
        """Check if hash exists in our records"""
        return file_hash in self.video_hashes

    def add_hash(self, file_hash: str, metadata: dict):
        """Add a new hash to our records"""
        self.video_hashes[file_hash] = metadata
        self._save_hashes()

    def _save_hashes(self):
        """Save hashes to file"""
        try:
            with open(VIDEO_HASH_FILE, 'w') as f:
                json.dump(self.video_hashes, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving video hashes: {e}")

    def is_message_processed(self, message_id: int) -> bool:
        """Check if message has already been processed"""
        return message_id in self.seen_message_ids

    def mark_message_processed(self, message_id: int):
        """Mark a message as processed"""
        self.seen_message_ids.add(message_id)