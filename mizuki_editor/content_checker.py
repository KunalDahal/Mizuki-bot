import logging
import asyncio
from typing import List, Dict, Optional, Union
from collections import defaultdict
from telegram import Bot, InputMediaPhoto, InputMediaVideo, Message
from telegram.constants import ParseMode
from util import get_target_channel, get_bot_token_2, load_banned_words
from mizuki_editor.hash import _load_hash_data
from mizuki_editor.processor import Processor
from mizuki_editor.editor import Editor

logger = logging.getLogger(__name__)

class ContentChecker:
    def __init__(self):
        self.hash_data = _load_hash_data()
        self.banned_words = load_banned_words()
        self.media_group_cache = defaultdict(list)
        self.bot = Bot(token=get_bot_token_2())
        self.processor = Processor(self.hash_data, self.banned_words, self)
        self.editor = Editor()
    
    def _contains_banned_words(self, text: str) -> bool:
        """Check if text contains any banned words"""
        if not text or not self.banned_words:
            return False
            
        text_lower = text.lower()
        return any(word.lower() in text_lower for word in self.banned_words)

    async def process_message(self, message: Message) -> Optional[Union[List[Dict], str]]:
        """Process a single message or add to media group cache"""
        if message.media_group_id:
            # Add to media group cache and process if first in group
            self.media_group_cache[message.media_group_id].append(message)
            if len(self.media_group_cache[message.media_group_id]) == 1:
                asyncio.create_task(self._process_complete_media_group(message.media_group_id))
            return None
        return await self._process_single_message(message)

    async def _process_single_message(self, message: Message) -> Optional[Union[List[Dict], str]]:
        """Process a single message (not part of a media group)"""
        caption = message.caption or message.text or ""
        
        # Process caption through text processor
        processed_caption = await self.editor.process(caption)
        
        # Banned words check
        if self._contains_banned_words(processed_caption):
            logger.warning("Message contains banned words - skipping")
            return None
        
        media_hashes = await self.processor._generate_media_hashes(message)
        
        # Handle text-only messages
        if not media_hashes and message.text:
            return processed_caption
        
        # Check for duplicates
        valid_files = []
        for media in media_hashes:
            if not await self.processor._check_duplicates([media]):
                media['processed_caption'] = processed_caption
                valid_files.append(media)
        
        if not valid_files:
            logger.info("No valid files after duplicate check")
            return None
        
        # Add to hash database
        await self.processor._add_to_hash_data(self.hash_data, processed_caption, valid_files)
        
        return valid_files

    async def _process_complete_media_group(self, group_id: str):
        """Process a complete media group after all parts are received"""
        await asyncio.sleep(2)  # Wait for all parts to arrive
        
        messages = self.media_group_cache.pop(group_id, [])
        if not messages:
            return

        # Get caption from first message that has one
        caption = next((msg.caption for msg in messages if msg.caption), "")
        
        # Process all media in the group
        media_list = []
        for msg in messages:
            media_hashes = await self.processor._generate_media_hashes(msg)
            if media_hashes:
                media_list.extend(media_hashes)
        
        if not media_list:
            return
        
        # Process caption through text processor
        processed_caption = await self.editor.process(caption)
        
        # Banned words check
        if self._contains_banned_words(processed_caption):
            logger.warning("Media group contains banned words - skipping")
            return
        
        # Check for duplicates
        valid_files = []
        for media in media_list:
            if not await self.processor._check_duplicates([media]):
                valid_files.append(media)
        
        if not valid_files:
            logger.info("All media in group are duplicates - skipping")
            return
        
        # Add to hash database (only add valid files)
        for media in valid_files:
            media['processed_caption'] = processed_caption
        
        await self.processor._add_to_hash_data(self.hash_data, processed_caption, valid_files)
        
        # Forward to target channels
        await self.forward_media_group(valid_files, processed_caption)

    async def forward_media_group(self, media_list: List[Dict], caption: str):
        """Forward a media group to all target channels with caption"""
        target_ids = get_target_channel()
        if not target_ids:
            logger.warning("No target channels configured")
            return

        for target_id in target_ids:
            try:
                # Build media group for forwarding
                media_group = []
                for i, item in enumerate(media_list):
                    if item['type'] == 'photo':
                        media_type = InputMediaPhoto
                    elif item['type'] in ['video', 'document']:
                        media_type = InputMediaVideo
                    else:
                        continue
                    
                    # Apply caption only to first item
                    if i == 0:
                        # Properly escape special characters for MarkdownV2
                        media_caption = caption.replace('.', r'\.').replace('-', r'\-').replace('!', r'\!')
                        parse_mode = ParseMode.MARKDOWN_V2
                    else:
                        media_caption = None
                        parse_mode = None
                    
                    # Truncate caption if too long
                    if media_caption and len(media_caption) > 1024:
                        media_caption = media_caption[:1000] + "... [TRUNCATED]"
                    
                    media_group.append(media_type(
                        media=item['file_id'],
                        caption=media_caption,
                        parse_mode=parse_mode
                    ))
                
                await self.bot.send_media_group(
                    chat_id=target_id,
                    media=media_group
                )
                logger.info(f"Successfully forwarded media group with {len(media_list)} items to channel {target_id}")
            except Exception as e:
                logger.error(f"Failed to forward media group to channel {target_id}: {e}")