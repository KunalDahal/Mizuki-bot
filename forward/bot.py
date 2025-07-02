from telegram.ext import Application, ContextTypes, CommandHandler,MessageHandler,filters
from telegram import Update
from util import get_bot_token_2
from forward.post import handle_forwarded_message
from commands.maintainence import  HealthMonitor
import logging
from commands.admin import admin_only
import asyncio
from forward.processor import Processor

logger = logging.getLogger(__name__)

health_monitor = HealthMonitor()

@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛡️ This is an admin-only command")

def setup_bot():
    application = Application.builder().token(get_bot_token_2()).build()
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(MessageHandler(
        filters.FORWARDED & (filters.TEXT | filters.PHOTO | filters.VIDEO),
        handle_forwarded_message
    ))


    return application

async def run_bot(monitor):
    """Run the Telegram bot and Telthon monitor concurrently"""
    application = setup_bot()

    processor = Processor()
    application.bot_data['processor'] = processor
    
    application.bot_data['monitor'] = monitor
    application.bot_data['health_monitor'] = health_monitor
    
    try:

        monitor_task = asyncio.create_task(monitor.run(), name="monitor")
        await asyncio.sleep(2) 

        bot_task = asyncio.create_task(run_bot_only(application), name="bot")
        
        logger.info("Starting bot and monitor...")
        await asyncio.gather(bot_task, monitor_task)
        logger.info("Both tasks completed")
        
    except asyncio.CancelledError:
        logger.info("Tasks cancelled gracefully")
    except Exception as e:
        logger.critical(f"Error in tasks: {e}", exc_info=True)
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

    while True:
        await asyncio.sleep(3600)