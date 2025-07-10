import asyncio
from telegram.ext import Application
from mizuki_editor.limit.config import get_bot_token_2
from mizuki.start import get_start_handler
from mizuki.upvote import get_upvote_handlers
from mizuki.request import get_request_handler
from mizuki.approve import get_approve_handler
from mizuki_editor.limit.monitor import VideoMonitor
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def run_bot():
    """Run the Telegram bot"""
    application = Application.builder().token(get_bot_token_2()).build()
    
    # Add handlers
    application.add_handler(get_start_handler())
    application.add_handlers(get_upvote_handlers())
    application.add_handler(get_request_handler())
    application.add_handler(get_approve_handler())
    
    # Start the bot
    await application.initialize()
    await application.start()
    print("Bot started...")
    await application.updater.start_polling()

async def main():
    """Main function to run both bot and monitor"""
    bot_task = asyncio.create_task(run_bot())
    monitor = VideoMonitor()
    monitor_task = asyncio.create_task(monitor.start())
    
    await asyncio.gather(bot_task, monitor_task)

if __name__ == '__main__':
    asyncio.run(main())