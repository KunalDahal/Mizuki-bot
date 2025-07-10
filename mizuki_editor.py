import logging
import asyncio
from mizuki_editor.monitor.monitor import ChannelMonitor
from mizuki_editor.main import handle_forwarded_message
from telegram.ext import Application, MessageHandler, filters, CommandHandler, ContextTypes
from util import get_bot_token_2, get_admin_ids
from mizuki_editor.monitor.sync import sync_channel_files
from telegram import Update
from typing import Optional
from mizuki_editor.content_checker import ContentChecker

# Import all command handlers from mizuki
from mizuki_editor.commands import (
    banned, channel, help, list, maintainence,
    remove, replace,  
    replace_emoji, symbol, start
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def error_handler(update: Optional[Update], context: ContextTypes.DEFAULT_TYPE):
    logger.error(f'Update {update} caused error: {context.error}', exc_info=context.error)
    if update and update.effective_message:
        await update.effective_message.reply_text('An error occurred. Please try again.')

def load_mizuki_handlers(application):
    """Load all command handlers from mizuki into the application"""
    try:
        logger.info("Loading mizuki command handlers...")
        
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
        
        # Replace word handlers
        for handler in replace.get_rep_handlers():
            application.add_handler(handler)
            
        # Emoji replacement handlers
        for handler in replace_emoji.get_handlers():
            application.add_handler(handler)
            
        # Symbol handlers
        for handler in symbol.get_handlers():
            application.add_handler(handler)
            
        logger.info("All mizuki handlers loaded successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to load mizuki handlers: {e}")
        return False

async def run_bot():
    restart_count = 0
    max_restarts = 5
    restart_delay = 10
    
    while restart_count < max_restarts:
        application = None
        monitor = None
        monitor_task = None
        sync_task = None
        
        try:
            application = Application.builder() \
                .token(get_bot_token_2()) \
                .read_timeout(30) \
                .write_timeout(30) \
                .build()
            
            application.bot_data['content_checker'] = ContentChecker()
            application.bot_data['admin_ids'] = get_admin_ids()
            
            sync_task = asyncio.create_task(sync_channel_files())
            
            monitor = ChannelMonitor()
            monitor_task = asyncio.create_task(monitor.run())
            
            # Load all mizuki command handlers
            if not load_mizuki_handlers(application):
                logger.error("Failed to load one or more mizuki handlers")
                return
            # Original editor handlers
            admin_filter = filters.User(user_id=get_admin_ids())
            application.add_handler(
                MessageHandler(
                    admin_filter & 
                    (filters.PHOTO | filters.VIDEO | filters.TEXT),
                    handle_forwarded_message
                )
            )
            
            application.add_error_handler(error_handler)
            
            logger.info("Starting bot application...")
            await application.initialize()
            await application.start()
            
            await application.updater.start_polling()
            logger.info("Polling started successfully")
            
            while True:
                await asyncio.sleep(5)
                if monitor_task.done():
                    logger.error("Monitor task stopped unexpectedly!")
                    raise RuntimeError("Monitor task stopped")
                if sync_task.done():
                    logger.error("Sync task stopped unexpectedly!")
                    raise RuntimeError("Sync task stopped")
                
        except asyncio.CancelledError:
            logger.info("Shutdown requested...")
            break
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            restart_count += 1
            if restart_count < max_restarts:
                logger.info(f"Restarting in {restart_delay} seconds... (attempt {restart_count}/{max_restarts})")
                await asyncio.sleep(restart_delay)
            else:
                logger.error("Max restart attempts reached")
                break
        finally:
            logger.info("Cleaning up resources...")
            try:
                if monitor:
                    monitor.running = False
                    await asyncio.sleep(0.5)
                
                if monitor_task:
                    monitor_task.cancel()
                    try:
                        await monitor_task
                    except asyncio.CancelledError:
                        pass
                
                if sync_task:
                    sync_task.cancel()
                    try:
                        await sync_task
                    except asyncio.CancelledError:
                        pass
                
                if application:
                    try:
                        await application.updater.stop()
                    except Exception as e:
                        logger.error(f"Error stopping updater: {e}")
                    try:
                        await application.stop()
                    except Exception as e:
                        logger.error(f"Error stopping application: {e}")
                    try:
                        await application.shutdown()
                    except Exception as e:
                        logger.error(f"Error shutting down application: {e}")
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")

async def main():
    try:
        await run_bot()
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
    finally:
        logger.info("Application fully stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application fully stopped")