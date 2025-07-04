import logging
from telegram.ext import Application
from mizuki import (
    banned, channel, help, list, maintainence,
    remove, replace, start, approve, request
)
from util import get_bot_token, setup_logging

def main():
    """Start the bot."""
    # Set up logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Create the Application
        application = Application.builder().token(get_bot_token()).build()
        
        # Add all command handlers
        application.add_handler(start.get_start_handler())
        application.add_handler(help.get_help_handler())
        
        # Add banned words handlers
        for handler in banned.get_banned_handlers():
            application.add_handler(handler)
        
        # Add channel handlers
        application.add_handler(channel.get_add_channel_handler())
        application.add_handler(channel.get_remove_channel_handler())
        
        # Add list handlers
        for handler in list.get_list_handlers():
            application.add_handler(handler)
        
        # Add maintenance handlers
        for handler in maintainence.get_maintenance_handlers():
            application.add_handler(handler)
        
        # Add remove word handlers
        application.add_handler(remove.get_add_remove_word_handler())
        application.add_handler(remove.get_remove_remove_word_handler())
        application.add_handler(request.get_request_handler())
        application.add_handler(approve.get_approve_handler())
        
        # Add replace word handlers
        for handler in replace.get_rep_handlers():
            application.add_handler(handler)

        # Run the bot
        logger.info("Bot is starting...")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")
        raise