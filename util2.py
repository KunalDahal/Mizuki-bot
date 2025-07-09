import os

JSON_FOLDER = "JSON"
os.makedirs(JSON_FOLDER, exist_ok=True)

HASH_FILE = os.path.join(JSON_FOLDER, "hash.json")


def source_id():
    return int(os.getenv("SIZE_ID"))

def ano_id():
    return int(os.getenv("SIZE_ID"))

def get_api_id_1():
    return int(os.getenv("API_ID"))


def get_api_hash_1():
    return os.getenv("API_HASH")


def get_session_string_1():
    session = os.getenv("SESSION_STRING")
    if not session:
        raise ValueError("SESSION_STRING not found in .env file")
    return session