import os
from dotenv import load_dotenv
import json
import re
import random
from typing import List,Union,Dict,Any


load_dotenv()
import logging

logger = logging.getLogger(__name__)

MAX_PHOTO_SIZE = 50_000_000 
MAX_VIDEO_SIZE = 150_000_000  
VIDEO_HASH_CHUNK_SIZE = 2_000_000  
VIDEO_HASH_SAMPLE_SIZE = 20_000_000 



JSON_FOLDER = "JSON"
os.makedirs(JSON_FOLDER, exist_ok=True)
REQ_FILE = os.path.join(JSON_FOLDER, "requests.json")
USER_FILE = os.path.join(JSON_FOLDER, "users.json")
TARGET_FILE = os.path.join(JSON_FOLDER, "ano_id.json")
SYMBOL_FILE = os.path.join(JSON_FOLDER, "symbol.json")
EMOJI_FILE = os.path.join(JSON_FOLDER, "emoji.json")
REPLACE_FILE = os.path.join(JSON_FOLDER, "replace.json")
REMOVE_FILE = os.path.join(JSON_FOLDER, "remove.json")
SOURCE_FILE = os.path.join(JSON_FOLDER, "source_id.json")
HASH_FILE = os.path.join(JSON_FOLDER, "hash.json")
BAN_FILE = os.path.join(JSON_FOLDER, "banned.json")
RECOVERY_FILE = os.path.join(JSON_FOLDER, "last_message_id.json")
MAX_HASH_ENTRIES = 1000

for file in [
    BAN_FILE,
    SOURCE_FILE,
    REMOVE_FILE,
    TARGET_FILE,
    SYMBOL_FILE
]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump([], f)

for file in [REPLACE_FILE, HASH_FILE,RECOVERY_FILE,EMOJI_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)

def get_dump_channel_id() -> int:
    channel_id = os.getenv("DUMP_CHANNEL_ID")
    if not channel_id:
        raise ValueError("DUMP_CHANNEL_ID not found in .env file")
    return int(channel_id)
def get_vid_channel_id() -> int:

    channel_id = os.getenv("VID_CHANNEL_ID")
    if not channel_id:
        raise ValueError("VID_CHANNEL_ID not found in .env file")
    return int(channel_id)

def get_target_channel() -> List[int]:
    if not os.path.exists(TARGET_FILE):
        raise ValueError("No target channel configured (file missing).")
    
    with open(TARGET_FILE, 'r') as f:
        channels = json.load(f)
    
    if not channels:
        raise ValueError("No target channel configured (empty list).")
    
    return [int(channel) for channel in channels]  

def add_target_channel(channel_id: int):
    """Add new forward target"""
    channels = get_target_channel()
    if channel_id not in channels:
        channels.append(channel_id)
        with open(TARGET_FILE, 'w') as f:
            json.dump(channels, f)

def remove_target_channel(channel_id: int):
    """Remove forward target"""
    channels = get_target_channel()
    if channel_id in channels:
        channels.remove(channel_id)
        with open(TARGET_FILE, 'w') as f:
            json.dump(channels, f)
            
def load_banned_words():
    with open(BAN_FILE, "r") as f:
        return json.load(f)

def save_banned_words(words):
    with open(BAN_FILE, "w") as f:
        json.dump(words, f)


def load_remove_words() -> List[str]:
    try:
        os.makedirs(JSON_FOLDER, exist_ok=True)

        if not os.path.exists(REMOVE_FILE):
            return []

        with open(REMOVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

            if isinstance(data, list):
                return data
            return data.get("words", [])

    except json.JSONDecodeError:
        print(f"Warning: {REMOVE_FILE} contains invalid JSON")
        return []
    except Exception as e:
        print(f"Error loading {REMOVE_FILE}: {e}")
        return []


def generate_post_id():
    return random.randint(10000, 99999)


def save_remove_words(words):
    os.makedirs(JSON_FOLDER, exist_ok=True)
    with open(REMOVE_FILE, "w") as f:
        json.dump(words, f, indent=2)


def get_bot_token():
    token = os.getenv("BOT_TOKEN_1")
    if not token:
        raise ValueError("BOT_TOKEN not found in .env file")
    return token


def get_bot_token_2():
    token = os.getenv("BOT_TOKEN_2")
    if not token:
        raise ValueError("BOT_TOKEN not found in .env file")
    return token

def load_replace_words():
    """Load word replacements from JSON file"""
    try:
        if not os.path.exists(REPLACE_FILE):
            return {}

        with open(REPLACE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading replace words: {e}")
        return {}


def save_replace_words(replace_dict):
    """Save word replacements to JSON file"""
    try:
        os.makedirs(JSON_FOLDER, exist_ok=True)
        with open(REPLACE_FILE, "w", encoding="utf-8") as f:
            json.dump(replace_dict, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving replace words: {e}")
        return False


def get_hf_token():
    token = os.getenv("HF_TOKEN")
    if not token:
        raise ValueError("HF_TOKEN not found in .env file")
    return token


def get_api_id():
    return int(os.getenv("API_ID"))


def get_api_hash():
    return os.getenv("API_HASH")


def get_session_string():
    session = os.getenv("SESSION_STRING")
    if not session:
        raise ValueError("SESSION_STRING not found in .env file")
    return session

def get_session_name():
    session = os.getenv("SESSION_NAME")
    if not session:
        raise ValueError("SESSION_NAME not found in .env file")
    return session


def get_bot_username():
    username = os.getenv("BOT_USERNAME")
    if not username:
        raise ValueError("BOT_USERNAME not found in .env file")
    return username.lstrip("@")


def load_channels():
    if not os.path.exists(SOURCE_FILE):
        return []
    with open(SOURCE_FILE, "r") as f:
        data = json.load(f)
    return [int(cid) for cid in data]


def save_channels(channel_list):
    os.makedirs(JSON_FOLDER, exist_ok=True)
    with open(SOURCE_FILE, "w") as f:
        json.dump(channel_list, f, indent=2)


def get_admin_ids():
    """Get list of admin user IDs from environment"""
    admin_ids = os.getenv('ADMIN_IDS', '').split(',')
    return [int(id.strip()) for id in admin_ids if id.strip().isdigit()]

def escape_markdown_v2(text: str) -> str:
    """Escape all special Markdown V2 characters"""
    if not text:
        return ""
    
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    
    pattern = f'([{"".join(re.escape(c) for c in escape_chars)}])'
    
    return re.sub(pattern, r'\\\1', text)

def load_emoji_replacements():
    """Load emoji replacements from JSON file"""
    try:
        if os.path.exists(EMOJI_FILE):
            with open(EMOJI_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Failed to load emoji replacements: {e}")
        return {}
    
def load_preserve_symbols() -> List[str]:
    """Load symbols to preserve during emoji removal"""
    try:
        if not os.path.exists(SYMBOL_FILE):
            return []
        with open(SYMBOL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load preserve symbols: {e}")
        return []
    
def get_admin_ids():
    """Get list of admin user IDs from environment"""
    admin_ids = os.getenv('ADMIN_IDS', '').split(',')
    return [int(id.strip()) for id in admin_ids if id.strip().isdigit()]

def get_source_id():
    return int(os.getenv("API_ID"))

def get_target_id():
    return int(os.getenv("API_ID"))

def get_api_id_1():
    return int(os.getenv("API_ID"))


def get_api_hash_1():
    return os.getenv("API_HASH")

def get_session_string_1():
    session = os.getenv("SESSION_STRING")
    if not session:
        raise ValueError("SESSION_STRING not found in .env file")
    return session

def get_bot_token_2():
    token = os.getenv("BOT_TOKEN_2")
    if not token:
        raise ValueError("BOT_TOKEN not found in .env file")
    return token


