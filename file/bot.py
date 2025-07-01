from telegram.ext import Application, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram import Update
from commands.channel import get_add_channel_handler
from commands.channel import get_remove_channel_handler
from commands.start import get_start_handler
from commands.remove import get_add_remove_word_handler
from commands.remove import get_remove_remove_word_handler
from commands.list import get_list_channels_handler
from util import get_bot_token
from client.post import button_handler, handle_forwarded_message
from commands.help import get_help_handler 
from commands.replace import get_handlers
from commands.maintainence import get_maintenance_handlers, HealthMonitor
import logging
from commands.admin import admin_only
import asyncio

logger = logging.getLogger(__name__)

# Health monitor instance (for /health and /ping)
health_monitor = HealthMonitor()

@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛡️ This is an admin-only command")

def setup_bot():
    application = Application.builder().token(get_bot_token()).build()

    # Add handlers individually
    application.add_handler(get_start_handler())
    application.add_handler(get_add_channel_handler())              # /a
    application.add_handler(get_remove_channel_handler())           # /r
    application.add_handler(get_add_remove_word_handler())          # /ar
    application.add_handler(get_remove_remove_word_handler())       # /rr
    
    # Add list handlers
    for handler in get_list_channels_handler():
        application.add_handler(handler)
    
    # Add replace handlers
    for handler in get_handlers():
        application.add_handler(handler)
    
    # Add maintenance handlers
    for handler in get_maintenance_handlers():
        application.add_handler(handler)
    
    application.add_handler(get_help_handler())
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(
        filters.FORWARDED, 
        handle_forwarded_message
    ))
    
    return application

async def run_bot(monitor):
    """Run the Telegram bot and Telthon monitor concurrently"""
    application = setup_bot()
    application.bot_data['monitor'] = monitor
    application.bot_data['health_monitor'] = health_monitor
    
    try:
        # Start the monitor first
        monitor_task = asyncio.create_task(monitor.run(), name="monitor")
        await asyncio.sleep(2)  # Give monitor a moment to start
        
        # Start the bot
        bot_task = asyncio.create_task(run_bot_only(application), name="bot")
        
        logger.info("Starting bot and monitor...")
        await asyncio.gather(bot_task, monitor_task)
        logger.info("Both tasks completed")
        
    except asyncio.CancelledError:
        logger.info("Tasks cancelled gracefully")
    except Exception as e:
        logger.critical(f"Error in tasks: {e}", exc_info=True)
        # Propagate error to restart
        raise
    finally:
        try:
            await application.stop()
        except Exception:
            pass
        logger.info("Bot stopped")

async def run_bot_only(application):
    """Run only the Telegram bot components"""
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logger.info("Bot is now running")
    
    # Keep running until cancelled
    while True:
        await asyncio.sleep(3600)