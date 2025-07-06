
import logging
from typing import List, Dict, Optional, Union
from telegram import Message
from mizuki_editor.editor import Editor
from util import get_admin_ids
from mizuki_editor.hash import _generate_media_hashes, _add_to_hash_data, _load_hash_data

logger = logging.getLogger(__name__)

class Processor:
    def __init__(self, hash_data, banned_words, content_checker):
        self.editor = Editor()
        self.hash_data = hash_data
        self.banned_words = banned_words
        self.content_checker = content_checker

    async def process_message(self, message: Message) -> Optional[Union[List[Dict], str]]:
        """Process a message through the content checker pipeline"""
        try:
            # Admin access check
            user_id = message.from_user.id if message.from_user else None
            if user_id not in get_admin_ids():
                logger.warning(f"Non-admin user {user_id} attempted direct post")
                return None
                
            return await self.content_checker.process_message(message)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return None

    async def _generate_media_hashes(self, message: Message) -> List[Dict]:
        """Generate hashes for media content"""
        return await _generate_media_hashes(message)

    async def _add_to_hash_data(self, hash_data, caption: str, media_hashes: List[Dict]):
        """Add new media hashes to the hash database"""
        await _add_to_hash_data(hash_data, caption, media_hashes)

    async def _check_duplicates(self, media_hashes: List[Dict]) -> bool:
        """Check if media hashes already exist in our database"""
        if not media_hashes:
            return False
            
        for media in media_hashes:
            for entry in self.hash_data.values():
                for existing_media in entry['media']:
                    if media['type'] == 'photo' and existing_media['type'] == 'photo':
                        if media['phash'] == existing_media['phash']:
                            return True
                    if media['sha256'] == existing_media['sha256']:
                        return True
        return False