import logging
import asyncio
from typing import List, Dict, Optional, Union
from collections import defaultdict
from telegram import Bot, InputMediaPhoto, InputMediaVideo, Message
from telegram.constants import ParseMode
from util import get_target_channel, get_bot_token_2, load_banned_words, get_dump_channel_id
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
        self.dump_channel = get_dump_channel_id()
    
    def _contains_banned_words(self, text: str) -> bool:
        """Check if text contains any banned words"""
        if not text or not self.banned_words:
            return False
            
        text_lower = text.lower()
        return any(word.lower() in text_lower for word in self.banned_words)

    async def process_message(self, message: Message) -> Optional[Union[List[Dict], str]]:
        """Process a single message or add to media group cache"""
        if message.media_group_id:
       
            self.media_group_cache[message.media_group_id].append(message)
            if len(self.media_group_cache[message.media_group_id]) == 1:
                asyncio.create_task(self._process_complete_media_group(message.media_group_id))
            return None
        return await self._process_single_message(message)

    async def _process_single_message(self, message: Message) -> Optional[Union[List[Dict], str]]:
        """Process a single message (not part of a media group)"""
        caption = message.caption or message.text or ""
        
        processed_caption = await self.editor.process(caption)
        
        if self._contains_banned_words(processed_caption):
            logger.warning("Message contains banned words - forwarding to dump channel")
            await self.forward_to_dump_channel([message], processed_caption)
            return None
        
        media_hashes = await self.processor._generate_media_hashes(message)
        
        large_media = [m for m in media_hashes if m.get('skipped')]
        if large_media:
            logger.warning("Large media detected - forwarding to dump channel")
            await self.forward_to_dump_channel([message], processed_caption)
         
            return None
        
        if not media_hashes and message.text:
            return processed_caption
        
        valid_files = []
        for media in media_hashes:
            if not await self.processor._check_duplicates([media]):
                media['processed_caption'] = processed_caption
                valid_files.append(media)
        
        if not valid_files:
            logger.info("No valid files after duplicate check")
            return None
        
        await self.processor._add_to_hash_data(self.hash_data, processed_caption, valid_files)
        
        return valid_files

    async def _process_complete_media_group(self, group_id: str):
        """Process a complete media group after all parts are received"""
        await asyncio.sleep(2) 
        
        messages = self.media_group_cache.pop(group_id, [])
        if not messages:
            return

        caption = next((msg.caption for msg in messages if msg.caption), "")
        
        processed_caption = await self.editor.process(caption)
        
        if self._contains_banned_words(processed_caption):
            logger.warning("Media group contains banned words - forwarding to dump channel")
            await self.forward_to_dump_channel(messages, processed_caption)
            return
        
        media_list = []
        large_media_files = []
        for msg in messages:
            media_hashes = await self.processor._generate_media_hashes(msg)
            for media in media_hashes:
                if media.get('skipped'):
                    large_media_files.append(media)
                else:
                    media_list.append(media)
        
        if large_media_files:
            logger.warning("Large media detected in group - forwarding to dump channel")
        
            large_media_messages = []
            for msg in messages:
                for media in large_media_files:
                    if media['file_id'] in [p.file_id for p in msg.photo] or \
                       (msg.video and msg.video.file_id == media['file_id']):
                        large_media_messages.append(msg)
                        break
            
            await self.forward_to_dump_channel(large_media_messages, processed_caption)
        
        if not media_list:
            logger.info("No non-large media left in the group")
            return
        
        valid_files = []
        for media in media_list:
            if not await self.processor._check_duplicates([media]):
                media['processed_caption'] = processed_caption
                valid_files.append(media)
        
        if not valid_files:
            logger.info("All non-large media in group are duplicates - skipping")
            return
        await self.processor._add_to_hash_data(self.hash_data, processed_caption, valid_files)
        
        await self.forward_media_group(valid_files, processed_caption)

    async def forward_media_group(self, media_list: List[Dict], caption: str):
        """Forward a media group to all target channels with caption"""
        target_ids = get_target_channel()
        if not target_ids:
            logger.warning("No target channels configured")
            return

        for target_id in target_ids:
            try:
                media_group = []
                for i, item in enumerate(media_list):
                    if item['type'] == 'photo':
                        media_type = InputMediaPhoto
                    elif item['type'] in ['video', 'document']:
                        media_type = InputMediaVideo
                    else:
                        continue
                    
                    if i == 0:
                        media_caption = caption
                        parse_mode = ParseMode.MARKDOWN_V2
                    else:
                        media_caption = None
                        parse_mode = None
                    
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
    
    async def forward_to_dump_channel(self, messages: List[Message], caption: str):
        """Forward messages to dump channel with formatted caption"""
        if not self.dump_channel:
            logger.warning("No dump channel configured")
            return
            
        try:
            if len(messages) == 1:
                msg = messages[0]
                if msg.text:
                    await self.bot.send_message(
                        chat_id=self.dump_channel,
                        text=caption,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                elif msg.photo:
                    await self.bot.send_photo(
                        chat_id=self.dump_channel,
                        photo=msg.photo[-1].file_id,
                        caption=caption,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                elif msg.video:
                    await self.bot.send_video(
                        chat_id=self.dump_channel,
                        video=msg.video.file_id,
                        caption=caption,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                elif msg.document:
                    await self.bot.send_document(
                        chat_id=self.dump_channel,
                        document=msg.document.file_id,
                        caption=caption,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
            else:
                media_group = []
                for i, msg in enumerate(messages):
                    if msg.photo:
                        media_type = InputMediaPhoto
                        media_id = msg.photo[-1].file_id
                    elif msg.video:
                        media_type = InputMediaVideo
                        media_id = msg.video.file_id
                    elif msg.document:
                        media_type = InputMediaVideo 
                        media_id = msg.document.file_id
                    else:
                        continue
                    
                    if i == 0:
                        media_caption = caption
                        parse_mode = ParseMode.MARKDOWN_V2
                    else:
                        media_caption = None
                        parse_mode = None
                    
                    media_group.append(media_type(
                        media=media_id,
                        caption=media_caption,
                        parse_mode=parse_mode
                    ))
                
                await self.bot.send_media_group(
                    chat_id=self.dump_channel,
                    media=media_group
                )
                logger.info(f"Forwarded media group with {len(media_group)} items to dump channel")
        except Exception as e:
            logger.error(f"Failed to forward to dump channel: {e}")