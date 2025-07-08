import logging
import sys
from telegram.ext import Application
from mizuki import (
    banned, channel, help, list, maintainence,
    remove, replace, start, approve, request,
    replace_emoji, symbol, upvote
)
from util import get_bot_token

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def load_handlers(application):
    """Load all command handlers into the application"""
    try:
        logger.info("Loading command handlers...")
        
        # Start and help commands
        application.add_handler(start.get_start_handler())
        application.add_handler(help.get_help_handler())
        
        # Banned words handlers
        for handler in banned.get_banned_handlers():
            application.add_handler(handler)
        
        # Channel handlers
        application.add_handler(channel.get_add_channel_handler())
        application.add_handler(channel.get_remove_channel_handler())
        
        # List handlers
        for handler in list.get_list_handlers():
            application.add_handler(handler)
        
        # Maintenance handlers
        for handler in maintainence.get_maintenance_handlers():
            application.add_handler(handler)
        
        # Remove word handlers
        application.add_handler(remove.get_add_remove_word_handler())
        application.add_handler(remove.get_remove_remove_word_handler())
        
        # Request system handlers
        application.add_handler(request.get_request_handler())
        application.add_handler(approve.get_approve_handler())
        
        # Replace word handlers
        for handler in replace.get_rep_handlers():
            application.add_handler(handler)
            
        # Emoji replacement handlers
        for handler in replace_emoji.get_handlers():
            application.add_handler(handler)
            
        # Symbol handlers
        for handler in symbol.get_handlers():
            application.add_handler(handler)
            
        # Upvote system handlers
        for handler in upvote.get_upvote_handlers():
            application.add_handler(handler)
            
        logger.info("All handlers loaded successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to load handlers: {e}")
        return False

def main():
    """Start the bot."""
    try:
        logger.info("Initializing bot application...")
        
        # Create the Application
        application = Application.builder().token(get_bot_token()).build()
        
        # Load all handlers
        if not load_handlers(application):
            logger.error("Failed to load one or more handlers")
            return
        
        # Run the bot
        logger.info("Bot is starting... Press Ctrl+C to stop")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()