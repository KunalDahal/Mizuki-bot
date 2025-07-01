from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from util import get_api_hash, get_api_id
import os

def generate_session():
    api_id = get_api_id()
    api_hash = get_api_hash()
    
    # Create client without automatic sign-in
    client = TelegramClient(StringSession(), api_id, api_hash)
    client.connect()
    
    if not client.is_user_authorized():
        phone = input("Enter your phone number (international format): ")
        client.send_code_request(phone)
        code = input("Enter the code you received: ")
        
        try:
            client.sign_in(phone, code)
        except Exception as e:
            # Handle 2FA if needed
            if "password" in str(e).lower():
                password = input("Enter your 2FA password: ")
                client.sign_in(password=password)
            else:
                print(f"Error: {e}")
                return
    
    session_str = client.session.save()
    print("\nGenerated session string:", session_str)
    
    # Save to .env file
    with open('.env', 'a') as f:
        f.write(f"\nSESSION_STRING={session_str}")
    print("Session saved to .env file")
    
    client.disconnect()

if __name__ == '__main__':
    generate_session()