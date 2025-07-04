import re
from telegram import Bot, InputMediaPhoto, InputMediaVideo
from telegram.constants import ParseMode
from util import load_remove_words, load_replace_words,get_bot_token_2
import asyncio
from deep_translator import GoogleTranslator
import logging

logger = logging.getLogger(__name__)

class Processor:
    def __init__(self):
        self.remove_words = load_remove_words()
        self.replace_words = load_replace_words()
            
    def extract_links(self, text):
        """Extract all URLs from text"""
        if not text:
            return []
        url_pattern = re.compile(r'https?://\S+')
        return list(set(url_pattern.findall(text)))

    def remove_words_from_text(self, text):
        """Remove specified words from text"""
        if not text or not self.remove_words:
            return text
        pattern = re.compile(r'\b(' + '|'.join(re.escape(word) for word in self.remove_words) + r')\b', re.IGNORECASE)
        return pattern.sub('', text)

    def replace_words_in_text(self, text):
        """Replace specified words in text"""
        if not text or not self.replace_words:
            return text
        
        for original, replacement in self.replace_words.items():
            pattern = re.compile(re.escape(original), re.IGNORECASE)
            text = pattern.sub(replacement, text)
        return text

    def remove_emojis(self, text):
        """Remove emojis from text"""
        if not text:
            return text
        emoji_pattern = re.compile(
            "["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F700-\U0001F77F"  # alchemical symbols
            u"\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
            u"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
            u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            u"\U0001FA00-\U0001FA6F"  # Chess Symbols
            u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            u"\U00002702-\U000027B0"  # Dingbats
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        return emoji_pattern.sub(r'', text)

    def translate_text(self, text):
        """Translate text using Google Translate"""
        try:
            if not text:
                return ""
                
            translated = GoogleTranslator(source='auto', target='en').translate(text)
            return translated if translated else text
        except Exception as e:
            logger.error(f"Translation failed: {str(e)}")
            return text

    def custom_escape_markdown(self, text):
        """Escape MarkdownV2 reserved characters without over-escaping"""
        if not text:
            return ""
        # Escape backslashes first
        text = text.replace('\\', '\\\\')
        escape_chars = '_*[]()~`>#+-=|{}.!'
        pattern = r'(?<!\\)([' + re.escape(escape_chars) + r'])'
        return re.sub(pattern, r'\\\1', text)

    async def process(self, caption):
        
        if caption is None:
            caption = ""

        links = self.extract_links(caption)
        
        url_removed = re.sub(r'https?://\S+', '', caption)
        
        translated = self.translate_text(url_removed)
        
        no_emojis = self.remove_emojis(translated)
        
        removed = self.remove_words_from_text(no_emojis)
        replaced = self.replace_words_in_text(removed).strip()
        
        main_text = self.custom_escape_markdown(replaced)
        
        formatted_text = f"_*{main_text}*_"
        
        if links:
            link_list = []
            for idx, link in enumerate(links, 1):
                display_text = self.custom_escape_markdown(link)
                link_list.append(f"[Link {idx}]:({link})")
            formatted_text += "\n\n" + "\n".join(link_list)
        footer_text = "@Mizuki_Newsbot"
        footer_escaped = self.custom_escape_markdown(footer_text)
        footer = f"> _*{footer_escaped}*_"
        
        return f"{formatted_text}\n\n{footer}"
    
    async def forward_to_channel(self, content, is_group, target_channel_id, bot_token):
        """Forward processed content to target channel with HTML parsing"""
        bot = Bot(token=bot_token)
        
        try:
            if is_group:
                # Build media group
                media_group = []
                for i, media in enumerate(content):
                    media_type = InputMediaPhoto if media['type'] == 'photo' else InputMediaVideo
                    
                    # Apply processed caption only to first media
                    caption = media.get('processed_caption') if i == 0 else None
                    parse_mode = ParseMode.HTML if caption else None
                    
                    media_group.append(media_type(
                        media=media['file_id'],
                        caption=caption,
                        parse_mode=parse_mode
                    ))
                
                await bot.send_media_group(
                    chat_id=target_channel_id,
                    media=media_group
                )
            else:
                # Handle single message
                media = content[0]
                caption = media.get('processed_caption')
                parse_mode = ParseMode.MARKDOWN_V2 if caption else None
                
                if media['type'] == 'text':
                    await bot.send_message(
                        chat_id=target_channel_id,
                        text=caption,
                        parse_mode=parse_mode
                    )
                elif media['type'] == 'photo':
                    await bot.send_photo(
                        chat_id=target_channel_id,
                        photo=media['file_id'],
                        caption=caption,
                        parse_mode=parse_mode
                    )
                elif media['type'] == 'video':
                    await bot.send_video(
                        chat_id=target_channel_id,
                        video=media['file_id'],
                        caption=caption,
                        parse_mode=parse_mode
                    )
            
            return True
        except Exception as e:
            logger.error(f"Forward error: {e}")
            return False
    
    async def forward_to_targets(self, content, target_ids):
        bot = Bot(token=get_bot_token_2())  # Create bot instance
        
        for target_id in target_ids:
            try:
                # For media groups
                if isinstance(content, list):
                    media_group = []
                    for media in content:
                        if media['type'] == 'photo':
                            media_group.append(InputMediaPhoto(media['file_id']))
                        elif media['type'] == 'video':
                            media_group.append(InputMediaVideo(media['file_id']))
                    
                    # Add caption to first media item
                    if media_group and content[0].get('processed_caption'):
                        media_group[0].caption = content[0]['processed_caption']
                        media_group[0].parse_mode = ParseMode.MARKDOWN_V2
                    
                    await bot.send_media_group(
                        chat_id=target_id,
                        media=media_group
                    )
                
                # For single messages
                else:
                    media = content[0]
                    caption = media.get('processed_caption')
                    
                    if media['type'] == 'text':
                        await bot.send_message(
                            chat_id=target_id,
                            text=caption,
                            parse_mode=ParseMode.MARKDOWN_V2
                        )
                    elif media['type'] == 'photo':
                        await bot.send_photo(
                            chat_id=target_id,
                            photo=media['file_id'],
                            caption=caption,
                            parse_mode=ParseMode.MARKDOWN_V2
                        )
                    elif media['type'] == 'video':
                        await bot.send_video(
                            chat_id=target_id,
                            video=media['file_id'],
                            caption=caption,
                            parse_mode=ParseMode.MARKDOWN_V2
                        )
                
                await asyncio.sleep(1)  # Rate limiting
            except Exception as e:
                logger.error(f"Forward error to {target_id}: {e}")