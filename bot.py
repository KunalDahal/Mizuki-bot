import logging
import threading
import asyncio
from mizuki_editor.monitor.monitor import ChannelMonitor
from mizuki_editor.main import handle_forwarded_message
from telegram.ext import Application, MessageHandler, filters, CommandHandler, ContextTypes
from util import get_bot_token_2, get_admin_ids,get_bot_token
from mizuki_editor.monitor.sync import sync_channel_files
from telegram import Update
from typing import Optional
from mizuki_editor.content_checker import ContentChecker
from mizuki_editor.limit.monitor import VideoMonitor
from mizuki.start import get_start_handler
from mizuki.upvote import get_upvote_handlers
from mizuki.request import get_request_handler
from mizuki.approve import get_approve_handler

# Import all command handlers from mizuki
from mizuki_editor.commands import (
    banned, channel, help, list, maintainence,
    remove, replace,  
    replace_emoji, symbol, start
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BotRunner:
    def __init__(self):
        self.running = True

    async def error_handler(self, update: Optional[Update], context: ContextTypes.DEFAULT_TYPE):
        logger.error(f'Update {update} caused error: {context.error}', exc_info=context.error)
        if update and update.effective_message:
            await update.effective_message.reply_text('An error occurred. Please try again.')

    def load_mizuki_handlers(self, application):
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

    async def run_mizuki_bot(self):
        """Run the Mizuki Editor bot"""
        restart_count = 0
        max_restarts = 5
        restart_delay = 10
        
        while restart_count < max_restarts and self.running:
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
                if not self.load_mizuki_handlers(application):
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
                
                application.add_error_handler(self.error_handler)
                
                logger.info("Starting mizuki bot application...")
                await application.initialize()
                await application.start()
                
                await application.updater.start_polling()
                logger.info("Mizuki bot polling started successfully")
                
                while self.running:
                    await asyncio.sleep(5)
                    if monitor_task.done():
                        logger.error("Monitor task stopped unexpectedly!")
                        raise RuntimeError("Monitor task stopped")
                    if sync_task.done():
                        logger.error("Sync task stopped unexpectedly!")
                        raise RuntimeError("Sync task stopped")
                    
            except asyncio.CancelledError:
                logger.info("Mizuki bot shutdown requested...")
                break
            except Exception as e:
                logger.error(f"Mizuki bot fatal error: {e}", exc_info=True)
                restart_count += 1
                if restart_count < max_restarts and self.running:
                    logger.info(f"Restarting mizuki bot in {restart_delay} seconds... (attempt {restart_count}/{max_restarts})")
                    await asyncio.sleep(restart_delay)
                else:
                    logger.error("Max restart attempts reached for mizuki bot")
                    break
            finally:
                logger.info("Cleaning up mizuki bot resources...")
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
                            logger.error(f"Error stopping mizuki updater: {e}")
                        try:
                            await application.stop()
                        except Exception as e:
                            logger.error(f"Error stopping mizuki application: {e}")
                        try:
                            await application.shutdown()
                        except Exception as e:
                            logger.error(f"Error shutting down mizuki application: {e}")
                except Exception as e:
                    logger.error(f"Error during mizuki bot shutdown: {e}")

    async def run_ses_bot(self):
        """Run the SES Telegram bot"""
        while self.running:
            try:
                application = Application.builder().token(get_bot_token()).build()
                
                # Add handlers
                application.add_handler(get_start_handler())
                application.add_handlers(get_upvote_handlers())
                application.add_handler(get_request_handler())
                application.add_handler(get_approve_handler())
                
                # Start the bot
                await application.initialize()
                await application.start()
                logger.info("SES bot started...")
                await application.updater.start_polling()
                
                while self.running:
                    await asyncio.sleep(5)
                    
            except Exception as e:
                logger.error(f"SES bot error: {e}", exc_info=True)
                if self.running:
                    logger.info("Restarting SES bot in 10 seconds...")
                    await asyncio.sleep(10)
            finally:
                if application:
                    try:
                        await application.updater.stop()
                        await application.stop()
                        await application.shutdown()
                    except Exception as e:
                        logger.error(f"Error shutting down SES bot: {e}")

    async def run_video_monitor(self):
        """Run the video monitor"""
        monitor = VideoMonitor()
        while self.running:
            try:
                await monitor.start()
            except Exception as e:
                logger.error(f"Video monitor error: {e}", exc_info=True)
                if self.running:
                    logger.info("Restarting video monitor in 10 seconds...")
                    await asyncio.sleep(10)

    async def run_channel_monitor(self):
        """Run the channel monitor"""
        monitor = ChannelMonitor()
        while self.running:
            try:
                await monitor.run()
            except Exception as e:
                logger.error(f"Channel monitor error: {e}", exc_info=True)
                if self.running:
                    logger.info("Restarting channel monitor in 10 seconds...")
                    await asyncio.sleep(10)

    def start_mizuki_bot(self):
        asyncio.run(self.run_mizuki_bot())

    def start_ses_bot(self):
        asyncio.run(self.run_ses_bot())

    def start_video_monitor(self):
        asyncio.run(self.run_video_monitor())

    def start_channel_monitor(self):
        """Run the channel monitor in its own thread with proper event loop"""
        def run_monitor():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.run_channel_monitor())
            finally:
                loop.close()

        threading.Thread(target=run_monitor, name="ChannelMonitor").start()

    def stop(self):
        self.running = False

def main():
    bot_runner = BotRunner()
    
    try:
        # Create and start threads for each process
        threads = [
            threading.Thread(target=bot_runner.start_mizuki_bot, name="MizukiBot"),
            threading.Thread(target=bot_runner.start_ses_bot, name="SESBot"),
            threading.Thread(target=bot_runner.start_video_monitor, name="VideoMonitor"),
            threading.Thread(target=bot_runner.start_channel_monitor, name="ChannelMonitor")
        ]
        
        for thread in threads:
            thread.daemon = True
            thread.start()
        
        # Wait for all threads to complete (they won't unless interrupted)
        for thread in threads:
            thread.join()
            
    except KeyboardInterrupt:
        logger.info("Shutting down all bots...")
        bot_runner.stop()
        
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        logger.info("All bots stopped")

if __name__ == "__main__":
    main()