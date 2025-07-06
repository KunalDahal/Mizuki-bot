import re
import logging
from deep_translator import GoogleTranslator
from util import load_remove_words, load_replace_words, escape_markdown_v2
from summa import summarizer

logger = logging.getLogger(__name__)

class Editor:
    def __init__(self):
        self.remove_words = load_remove_words()
        self.replace_words = load_replace_words()
            
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

        # Summarize to around 100 words
        summary = summarizer.summarize(text, words=100)
        if not summary:
            return text

        # Split into sentences while preserving punctuation
        sentences = re.split(r'(?<=[.!?])\s+', summary)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Group into paragraphs of ~20 words
        paragraphs = []
        current_para = []
        current_words = 0

        for sentence in sentences:
            sentence_words = len(sentence.split())
            if current_words + sentence_words > 20:
                # Make paragraph
                paragraphs.append(' '.join(current_para))
                current_para = []
                current_words = 0
            current_para.append(sentence)
            current_words += sentence_words

        # Add any leftover
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

    def remove_emojis(self, text):
        """Remove emojis from text"""
        if not text:
            return text
        emoji_pattern = re.compile(
            "[" 
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F700-\U0001F77F"
            u"\U0001F780-\U0001F7FF"
            u"\U0001F800-\U0001F8FF"
            u"\U0001F900-\U0001F9FF"
            u"\U0001FA00-\U0001FA6F"
            u"\U0001FA70-\U0001FAFF"
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        return emoji_pattern.sub(r'', text)

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

        # Extract but we won't use to add links at bottom
        links = self.extract_links(caption)
        
        # Processing pipeline
        url_removed = re.sub(r'https?://\S+', '', caption)
        no_emojis = self.remove_emojis(url_removed)
        translated = self.translate_text(no_emojis)
        removed = self.remove_words_from_text(translated)
        replaced = self.replace_words_in_text(removed.strip())
        summarized = self.summarize_text(replaced)

        main_text = escape_markdown_v2(summarized)
        formatted_text = f"_*{main_text}*_" if main_text else ""

        # Footer only
        footer_text = "@Mizuki_Newsbot"
        footer_escaped = escape_markdown_v2(footer_text)
        footer = f"\n\n> _*{footer_escaped}*_"

        return f"{formatted_text}{footer}"
