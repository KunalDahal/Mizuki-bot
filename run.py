import logging
from client.monitor import ChannelMonitor
from file.bot import run_bot

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    monitor = ChannelMonitor()
    await run_bot(monitor)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())