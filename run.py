import logging
import asyncio
from forward.monitor import ChannelMonitor
from forward.bot import run_bot
from duplicate.mizuki import main as mizuki_main

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def run_mizuki():
    """Run the mizuki bot"""
    try:
        await mizuki_main()
    except Exception as e:
        logger.error(f"Mizuki bot crashed: {e}")
        raise

async def run_bot_wrapper(monitor):
    """Wrapper for the bot run function"""
    try:
        await run_bot(monitor)
    except Exception as e:
        logger.error(f"Main bot crashed: {e}")
        raise

async def main():
    # Setup your bots
    monitor = ChannelMonitor()
    
    # Create tasks for both bots
    mizuki_task = asyncio.create_task(run_mizuki(), name="mizuki_bot")
    bot_task = asyncio.create_task(run_bot_wrapper(monitor), name="main_bot")
    
    logger.info("Starting both bots...")
    
    # Wait for both bots to run (they will run concurrently)
    await asyncio.gather(mizuki_task, bot_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")