import os
import json
from dotenv import load_dotenv
load_dotenv()

JSON_FOLDER = "JSON"
os.makedirs(JSON_FOLDER, exist_ok=True)
VIDEO_HASH_FILE = os.path.join(JSON_FOLDER, "video.json")
TARGET_FILE = os.path.join(JSON_FOLDER, "ano_id.json")

for file in [
    TARGET_FILE
]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump([], f)

# ensure dict files
for file in [VIDEO_HASH_FILE ]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)
            
def get_admin_ids():
    """Get list of admin user IDs from environment"""
    admin_ids = os.getenv('ADMIN_IDS', '').split(',')
    return [int(id.strip()) for id in admin_ids if id.strip().isdigit()]

def get_source_id():
    return int(os.getenv("VID_CHANNEL_ID"))

def get_target_id():
    return int(os.getenv("ANO_ID"))

def get_api_id_1():
    return int(os.getenv("API_ID"))


def get_api_hash_1():
    return os.getenv("API_HASH")

def get_session_string_1():
    session = os.getenv("SESSION_STRING")
    if not session:
        raise ValueError("SESSION_STRING_1 not found in .env file")
    return session

def escape_markdown_v2(text: str) -> str:
    """Escape special Markdown V2 characters while preserving blockquotes (>), spoilers (||), bold (*), and italic (_)"""
    if not text:
        return ""

    # Characters to escape (excluding >, |, *, _)
    escape_chars = r'[]()>~`#+-=|*_{}.!'
    
    # Escape each problematic character individually
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    
    return text