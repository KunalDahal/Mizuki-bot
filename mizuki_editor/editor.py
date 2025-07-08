import re
import logging
from deep_translator import GoogleTranslator
from util import load_remove_words, load_replace_words, escape_markdown_v2, load_emoji_replacements, load_preserve_symbols
from summa import summarizer

logger = logging.getLogger(__name__)

class Editor:
    def __init__(self):
        self.remove_words = load_remove_words()
        self.replace_words = load_replace_words()
        self.emoji_replacements = load_emoji_replacements()
        self.preserve_symbols = set(load_preserve_symbols())  
            
    def extract_links(self, text):
        """Extract all URLs from text"""
        if not text:
            return []
        url_pattern = re.compile(r'https?://\S+')
        return list(set(url_pattern.findall(text)))

    def summarize_text(self, text):
        word_count = len(text.split())
        if word_count <= 101:
            return text
        summary = summarizer.summarize(text, words=100)
        if not summary:
            return text

        sentences = re.split(r'(?<=[.!?])\s+', summary)
        sentences = [s.strip() for s in sentences if s.strip()]

        paragraphs = []
        current_para = []
        current_words = 0

        for sentence in sentences:
            sentence_words = len(sentence.split())
            if current_words + sentence_words > 20:
        
                paragraphs.append(' '.join(current_para))
                current_para = []
                current_words = 0
            current_para.append(sentence)
            current_words += sentence_words

        if current_para:
            paragraphs.append(' '.join(current_para))

        formatted_summary = '\n\n'.join(paragraphs)
        return formatted_summary.strip()

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

    def replace_emojis_with_symbols(self, text):
        """Replace emojis with their symbol equivalents"""
        if not text or not self.emoji_replacements:
            return text
        sorted_emojis = sorted(self.emoji_replacements.keys(), key=len, reverse=True)
        for emoji in sorted_emojis:
            symbol = self.emoji_replacements[emoji]
            text = text.replace(emoji, symbol)
        return text

    def remove_hashtags(self, text):
        """Remove all hashtags from text"""
        if not text:
            return text
        return re.sub(r'#\S+', '', text)

    def remove_emojis(self, text):
        """Remove emojis from text while preserving specified symbols"""
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
            
        def preserve_replace(match):
            char = match.group(0)
            return char if char in self.preserve_symbols else ''

        return emoji_pattern.sub(preserve_replace, text)

    def translate_text(self, text):
        try:
            if not text:
                return ""
            max_chunk_size = 5000
            chunks = [text[i:i+max_chunk_size] for i in range(0, len(text), max_chunk_size)]
            translated_chunks = []
            for chunk in chunks:
                translated = GoogleTranslator(source='auto', target='en').translate(chunk)
                if translated:
                    translated_chunks.append(translated)
            return " ".join(translated_chunks) if translated_chunks else text
        except Exception as e:
            logger.error(f"Translation failed: {str(e)}")
            return text

    async def process(self, caption):
        if caption is None:
            caption = ""

        links = self.extract_links(caption)
        replaced_emojis = self.replace_emojis_with_symbols(caption)
        url_removed = re.sub(r'https?://\S+', '', replaced_emojis)
        no_hashtags = self.remove_hashtags(url_removed)
        no_emojis = self.remove_emojis(no_hashtags)
        has_original_emojis = bool(re.search(
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
            "]", no_emojis, flags=re.UNICODE))
        translated = self.translate_text(no_emojis)
        removed = self.remove_words_from_text(translated)
        replaced = self.replace_words_in_text(removed.strip())
        summarized = self.summarize_text(replaced)

        main_text = escape_markdown_v2(summarized)
        footer_text = escape_markdown_v2("💠 ~ @Animes_News_Ocean")

        header = "> _*@Mizuki\\_Newsbot*_"
        header_new=f"||{header}||\n\n"
        
        if not has_original_emojis and main_text:
            main_text = f"❄️{main_text}"


        formatted_text = f"*{main_text}*" if main_text else ""
        footer = f"\n\n> _*{footer_text}*_"

        return f"{header_new}{formatted_text}{footer}"