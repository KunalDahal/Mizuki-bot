import asyncio
import threading
from mizuki_editor.mizuki_editor import MizukiEditor
from mizuki.mizuki import main as mizuki_main
from mizuki_editor.monitor import ChannelMonitor

def run_mizuki():
    mizuki_main()

def run_editor():
    editor = MizukiEditor()
    asyncio.run(editor.run())

async def run_monitor():
    monitor = ChannelMonitor()
    await monitor.run()

if __name__ == '__main__':
    # Start Mizuki Bot (commands)
    mizuki_thread = threading.Thread(target=run_mizuki)
    mizuki_thread.start()
    
    # Start Mizuki Editor
    editor_thread = threading.Thread(target=run_editor)
    editor_thread.start()
    
    # Start monitor in main thread
    asyncio.run(run_monitor())