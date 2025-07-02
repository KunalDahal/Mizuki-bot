import os
from dotenv import load_dotenv
import json
import random
from typing import List,Union
load_dotenv()

# Media size limits
MAX_PHOTO_SIZE = 50_000_000       # 50MB
MAX_VIDEO_SIZE = 150_000_000       # 150MB 
VIDEO_HASH_CHUNK_SIZE = 2_000_000  # 2MB chunks
VIDEO_HASH_SAMPLE_SIZE = 20_000_000 # 20MB to hash

JSON_FOLDER = "JSON"
os.makedirs(JSON_FOLDER, exist_ok=True)

USER_FILE=os.path.join(JSON_FOLDER, "users.json")
REPLACE_FILE=os.path.join(JSON_FOLDER, "replace.json")
REMOVE_FILE=os.path.join(JSON_FOLDER, "remove.json")
CHANNEL_FILE = os.path.join(JSON_FOLDER, "channel_id.json")
HASH_FILE = os.path.join(JSON_FOLDER, "hash.json")
BAN_FILE = os.path.join(JSON_FOLDER, "banned.json")
MAX_HASH_ENTRIES = 500

# ensure list files
for file in [BAN_FILE, CHANNEL_FILE, REMOVE_FILE, USER_FILE]:
    if not os.path.exists(file):
        with open(file, 'w') as f:
            json.dump([], f)

# ensure dict files
for file in [REPLACE_FILE, HASH_FILE]:
    if not os.path.exists(file):
        with open(file, 'w') as f:
            json.dump({}, f)

# Load banned words
def load_banned_words():
    with open(BAN_FILE, 'r') as f:
        return json.load(f)

# Save banned words
def save_banned_words(words):
    with open(BAN_FILE, 'w') as f:
        json.dump(words, f)
        
def load_remove_words() -> List[str]:
    try:
        # Create directory if it doesn't exist
        os.makedirs(JSON_FOLDER, exist_ok=True)
        
        # Return empty list if file doesn't exist
        if not os.path.exists(REMOVE_FILE):
            return []
            
        # Load and return words from file
        with open(REMOVE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Support both array format and object with 'words' key
            if isinstance(data, list):
                return data
            return data.get('words', [])
            
    except json.JSONDecodeError:
        # Handle corrupt JSON file
        print(f"Warning: {REMOVE_FILE} contains invalid JSON")
        return []
    except Exception as e:
        # Log other errors and return empty list
        print(f"Error loading {REMOVE_FILE}: {e}")
        return []
    
def generate_post_id():
    return random.randint(10000, 99999)

def save_remove_words(words):
    os.makedirs(JSON_FOLDER, exist_ok=True)
    with open(REMOVE_FILE, 'w') as f:
        json.dump(words, f, indent=2)
        
def get_bot_token():
    token = os.getenv('BOT_TOKEN_1')
    if not token:
        raise ValueError("BOT_TOKEN not found in .env file")
    return token
def get_bot_token_2():
    token = os.getenv('BOT_TOKEN_2')
    if not token:
        raise ValueError("BOT_TOKEN not found in .env file")
    return token


def load_replace_words():
    """Load word replacements from JSON file"""
    try:
        if not os.path.exists(REPLACE_FILE):
            return {}
        
        with open(REPLACE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading replace words: {e}")
        return {}

def save_replace_words(replace_dict):
    """Save word replacements to JSON file"""
    try:
        os.makedirs(JSON_FOLDER, exist_ok=True)
        with open(REPLACE_FILE, 'w', encoding='utf-8') as f:
            json.dump(replace_dict, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving replace words: {e}")
        return False

def get_hf_token():
    token = os.getenv('HF_TOKEN')
    if not token:
        raise ValueError("HF_TOKEN not found in .env file")
    return token

def get_api_id():
    return int(os.getenv('API_ID'))

def get_api_hash():
    return os.getenv('API_HASH')

def get_session_string():
    session = os.getenv('SESSION_STRING')
    if not session:
        raise ValueError("SESSION_STRING not found in .env file")
    return session

def get_session_name():
    session = os.getenv('SESSION_NAME')
    if not session:
        raise ValueError("SESSION_NAME not found in .env file")
    return session

def get_bot_username():
    username = os.getenv('BOT_USERNAME')
    if not username:
        raise ValueError("BOT_USERNAME not found in .env file")
    return username.lstrip('@')

def get_moderation_channel_id():
    channel_id = os.getenv('MODERATION_CHANNEL_ID')
    if not channel_id:
        raise ValueError("MODERATION_CHANNEL_ID not found in .env file")
    return int(channel_id)

def get_target_channel_id():
    channel_id = os.getenv('TARGET_ID')
    if not channel_id:
        raise ValueError("TARGET_ID not found in .env file")
    return int(channel_id)

def load_channels():
    if not os.path.exists(CHANNEL_FILE):
        return []
    with open(CHANNEL_FILE, 'r') as f:
        data = json.load(f)
    return [int(cid) for cid in data]

def save_channels(channel_list):
    os.makedirs(JSON_FOLDER, exist_ok=True)
    with open(CHANNEL_FILE, 'w') as f:
        json.dump(channel_list, f, indent=2)

def get_admin_ids():
    ids = os.getenv('ADMIN_IDS', '')
    return [int(id_str.strip()) for id_str in ids.split(',') if id_str.strip()]

def load_users() -> List[str]:
    try:

        os.makedirs(JSON_FOLDER, exist_ok=True)
        
        # Return empty list if file doesn't exist
        if not os.path.exists(USER_FILE):
            return []
            
        # Load and validate existing data
        with open(USER_FILE, 'r') as f:
            users = json.load(f)
            
            # Ensure we always return a list of strings
            if not isinstance(users, list):
                raise ValueError("Invalid data format in user.json")
                
            return [str(user_id) for user_id in users]
            
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error loading user data: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error loading users: {e}")
        return []

def save_users(user_ids: List[Union[str, int]]) -> bool:
    try:
        # Convert all IDs to strings and remove duplicates
        unique_users = list({str(uid) for uid in user_ids})
        
        # Create directory if it doesn't exist
        os.makedirs(JSON_FOLDER, exist_ok=True)
        
        # Write to file with pretty formatting
        with open(USER_FILE, 'w') as f:
            json.dump(unique_users, f, indent=2, ensure_ascii=False)
            
        return True
    except Exception as e:
        print(f"Error saving user data: {e}")
        return False

def add_user(user_id: Union[str, int]) -> bool:

    try:
        users = load_users()
        user_str = str(user_id)
        
        if user_str not in users:
            users.append(user_str)
            return save_users(users)
        return True  # Already exists
    except Exception as e:
        print(f"Error adding user: {e}")
        return False