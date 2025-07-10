import os
from typing import List,Union,Dict,Any
import json
from dotenv import load_dotenv
load_dotenv()

JSON_FOLDER = "JSON"
os.makedirs(JSON_FOLDER, exist_ok=True)
REQ_FILE = os.path.join(JSON_FOLDER, "requests.json")
USER_FILE = os.path.join(JSON_FOLDER, "users.json")
VIDEO_HASH_FILE = os.path.join(JSON_FOLDER, "video.json")
UPVOTE_FILE = os.path.join(JSON_FOLDER, "upvote.json")
TARGET_FILE = os.path.join(JSON_FOLDER, "ano_id.json")

for file in [
    TARGET_FILE,USER_FILE
]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump([], f)

# ensure dict files
for file in [REQ_FILE ,VIDEO_HASH_FILE,UPVOTE_FILE ]:
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

def get_bot_token_2():
    token = os.getenv("BOT_TOKEN_1")
    if not token:
        raise ValueError("BOT_TOKEN_1 not found in .env file")
    return token

def load_users() -> List[str]:
    try:

        os.makedirs(JSON_FOLDER, exist_ok=True)

        # Return empty list if file doesn't exist
        if not os.path.exists(USER_FILE):
            return []

        # Load and validate existing data
        with open(USER_FILE, "r") as f:
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
        with open(USER_FILE, "w") as f:
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
    
    

def load_upvotes() -> Dict[str, Any]:
    """Load upvote data from JSON file"""
    try:
        os.makedirs(JSON_FOLDER, exist_ok=True)
        if not os.path.exists(UPVOTE_FILE):
            return {"count": 0, "users": {}}
        
        with open(UPVOTE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "users" not in data:
                data["users"] = {}
            if "count" not in data:
                data["count"] = 0
            return data
    except Exception as e:
        print(f"Error loading upvote data: {e}")
        return {"count": 0, "users": {}}
    
def save_upvotes(data: Dict[str, Any]) -> bool:
    """Save upvote data to JSON file"""
    try:
        with open(UPVOTE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving upvote data: {e}")
        return False