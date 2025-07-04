import asyncio
import logging
from mizuki_editor.monitor import ChannelMonitor
from mizuki_editor.dup_ban import DupBanMonitor
from mizuki_editor.post import handle_forwarded_message
from telegram.ext import Application, MessageHandler, filters
from util import get_bot_token_2, get_dump_channel_id, get_target_channel, get_admin_ids
from mizuki_editor.sync import sync_channel_files

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
            
            # Store processor in bot_data
            from mizuki_editor.processor import Processor
            application.bot_data['processor'] = Processor()
            application.bot_data['admin_ids'] = get_admin_ids()
            
            # Start channel file sync task
            sync_task = asyncio.create_task(sync_channel_files())
            
            # Initialize and start monitor
            monitor = ChannelMonitor()
            monitor_task = asyncio.create_task(monitor.run())
            
            # Initialize DupBanMonitor
            dup_ban_monitor = DupBanMonitor(
                application=application,
                dump_channel_id=get_dump_channel_id()
            )
            await dup_ban_monitor.start()
            
            # Add message handler for admin messages only
            admin_filter = filters.User(user_id=get_admin_ids())
            application.add_handler(
                MessageHandler(
                    admin_filter & 
                    (filters.PHOTO | filters.VIDEO | filters.TEXT),
                    handle_forwarded_message
                )
            )
            
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
                    await asyncio.sleep(0.5)  # Give monitor time to stop
                
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
        # Run the bot with proper cleanup
        await run_bot()
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
    finally:
        logger.info("Application fully stopped")

if __name__ == "__main__":
    # Use asyncio.run() for proper event loop handling (Python 3.7+)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application fully stopped")