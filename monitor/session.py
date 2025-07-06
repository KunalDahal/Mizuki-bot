from telethon import TelegramClient
from telethon.sessions import StringSession
from util import get_session_string, get_api_hash, get_api_id
import logging

logger = logging.getLogger(__name__)

def create_session():
    session_string = get_session_string()
    if not session_string:
        raise ValueError("Session string not found in .env file")
    
    client = TelegramClient(
        session=StringSession(session_string),
        api_id=get_api_id(),
        api_hash=get_api_hash()
    )
    return client