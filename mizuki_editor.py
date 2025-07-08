import logging
import asyncio
from mizuki_editor.monitor.monitor import ChannelMonitor
from mizuki_editor.main import handle_forwarded_message
from telegram.ext import Application, MessageHandler, filters, CommandHandler,ContextTypes
from util import get_bot_token_2, get_admin_ids
from mizuki_editor.monitor.sync import sync_channel_files
from mizuki.admin import admin_only
from telegram import Update
from typing import Optional

# Import the ContentChecker from our refactored module
from mizuki_editor.content_checker import ContentChecker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_text(f'Hi {user.first_name}! This is the Mizuki Editor bot.')

@admin_only
async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send admin help message"""
    help_text = """
    👨‍💻 *Admin Commands*:
    /start - Start the bot
    /help - Show this help message
    
    📤 *Usage*:
    Forward messages or media to this bot:
    - Single messages with text
    - Single media with captions
    - Media groups with captions
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def error_handler(update: Optional[Update], context: ContextTypes.DEFAULT_TYPE):
    """Log errors and handle them gracefully."""
    logger.error(f'Update {update} caused error: {context.error}', exc_info=context.error)
    if update and update.effective_message:
        await update.effective_message.reply_text('An error occurred. Please try again.')

async def run_bot():
    """Main bot running coroutine with restart capabilities"""
    restart_count = 0
    max_restarts = 5
    restart_delay = 10
    
    while restart_count < max_restarts:
        application = None
        monitor = None
        monitor_task = None
        sync_task = None
        
        try:
            # Create application with timeout settings
            application = Application.builder() \
                .token(get_bot_token_2()) \
                .read_timeout(30) \
                .write_timeout(30) \
                .build()
            
            # Initialize ContentChecker and store in bot_data
            application.bot_data['content_checker'] = ContentChecker()
            application.bot_data['admin_ids'] = get_admin_ids()
            
            # Start channel file sync task
            sync_task = asyncio.create_task(sync_channel_files())
            
            # Initialize and start monitor
            monitor = ChannelMonitor()
            monitor_task = asyncio.create_task(monitor.run())
            
            # Add command handlers
            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("help", admin_help))
            
            # Add message handler for admin messages only
            admin_filter = filters.User(user_id=get_admin_ids())
            application.add_handler(
                MessageHandler(
                    admin_filter & 
                    (filters.PHOTO | filters.VIDEO | filters.TEXT),
                    handle_forwarded_message
                )
            )
            
            # Add error handler
            application.add_error_handler(error_handler)
            
            logger.info("Starting bot application...")
            await application.initialize()
            await application.start()
            await application.updater.start_polling()
            
            # Run until stopped
            while True:
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info("Shutdown requested...")
            break
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            restart_count += 1
            if restart_count < max_restarts:
                logger.info(f"Restarting in {restart_delay} seconds... (attempt {restart_count}/{max_restarts})")
                await asyncio.sleep(restart_delay)
            else:
                logger.error("Max restart attempts reached")
                break
        finally:
            # Shutdown sequence
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
    """Main entry point with proper event loop handling"""
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