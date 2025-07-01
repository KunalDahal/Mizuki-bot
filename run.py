import logging
from client.monitor import ChannelMonitor
from file.bot import run_bot
from aiohttp import web

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def health_check(request):
    return web.Response(text="Bot is running")

async def main():
    # Create a simple web application
    app = web.Application()
    app.router.add_get('/health', health_check)
    
    # Setup your bot
    monitor = ChannelMonitor()
    bot_task = asyncio.create_task(run_bot(monitor))
    
    # Setup web runner
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Bind to port provided by Render (default is 10000)
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, host='0.0.0.0', port=port)
    await site.start()
    
    # Run both bot and web server
    await bot_task

if __name__ == "__main__":
    import asyncio
    import os
    asyncio.run(main())