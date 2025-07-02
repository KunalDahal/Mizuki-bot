from telegram.ext import Application
from duplicate.media_monitor import SardarMonitor
import logging
from util import get_bot_token
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram import Update
from commands.channel import get_add_channel_handler
from commands.channel import get_remove_channel_handler
from commands.start import get_start_handler
from commands.remove import get_add_remove_word_handler
from commands.remove import get_remove_remove_word_handler
from commands.list import get_list_handlers
from commands.help import get_help_handler 
from commands.replace import get_rep_handlers
from commands.maintainence import get_maintenance_handlers
from commands.admin import admin_only
from forward.processor import Processor
import asyncio

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛡️ This is an admin-only command")

def setup_bot():
    application = Application.builder().token(get_bot_token()).build()
    application.bot_data['processor'] = Processor()
      
    # Add command handlers
    application.add_handler(get_start_handler())
    application.add_handler(get_add_channel_handler())              # /a
    application.add_handler(get_remove_channel_handler())           # /r
    application.add_handler(get_add_remove_word_handler())          # /ar
    application.add_handler(get_remove_remove_word_handler())  

    for handler in get_list_handlers():
        application.add_handler(handler)
    
    for handler in get_rep_handlers():
        application.add_handler(handler)

    for handler in get_maintenance_handlers():
        application.add_handler(handler)
    
    application.add_handler(get_help_handler())
    application.add_handler(CommandHandler("admin", admin_command))

    return application

async def main():
    # Initialize Telegram application with all handlers
    application = setup_bot()
    
    # Create and start the monitor
    monitor = SardarMonitor(application)
    application.bot_data['monitor'] = monitor 
    # Start the application
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Start the monitor after application is running
    await monitor.start()
    
    # Keep the application running until stopped
    while True:
        await asyncio.sleep(1)

async def shutdown(signal, loop, application, monitor):
    """Cleanup tasks tied to the service's shutdown."""
    logger.info(f"Received exit signal {signal.name}...")
    
    # Stop monitor first
    if monitor:
        await monitor.stop()
    
    # Then stop application
    if application:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
    
    loop.stop()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Run main coroutine
        loop.run_until_complete(main())
    except Exception as e:
        logger.exception("Bot crashed with error:")
    finally:
        loop.close()
        logger.info("Successfully shutdown the service")