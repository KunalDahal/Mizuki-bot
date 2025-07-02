import os
import sys
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from commands.admin import admin_only
import logging
from util import CHANNEL_FILE, REMOVE_FILE, REPLACE_FILE,BAN_FILE,HASH_FILE
import psutil
import time
import asyncio
import json

logger = logging.getLogger(__name__)

@admin_only
async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /restart command"""
    await update.message.reply_text("🔄 Restarting bot...")
    logger.info("Restart initiated by admin")
    
    # Gracefully shutdown first
    if 'application' in context.bot_data:
        await context.bot_data['application'].stop()
    
    # Restart the process
    os.execl(sys.executable, sys.executable, *sys.argv)

@admin_only
async def shutdown_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /shutdown command"""
    await update.message.reply_text("⏹️ Shutting down bot...")
    logger.info("Shutdown initiated by admin")
    
    if 'application' in context.bot_data:
        await context.bot_data['application'].stop()
    sys.exit(0)
@admin_only
async def reset_json(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /reset command to reset JSON files"""
    try:
        # Reset each file with appropriate empty structure
        files_to_reset = {
            CHANNEL_FILE: [],
            REMOVE_FILE: [],
            REPLACE_FILE: {},
            BAN_FILE: [],
            HASH_FILE : {}  
        }
        
        for file_path, default_value in files_to_reset.items():
            try:
                with open(file_path, 'w') as f:
                    json.dump(default_value, f, indent=2)
            except Exception as e:
                await update.message.reply_text(f"⚠️ Error resetting {os.path.basename(file_path)}: {e}")
                continue
        
        await update.message.reply_text("✅ All JSON files have been reset to default empty structures")
        
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error during reset: {e}")
    

class HealthMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.message_count = 0

    async def health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /health command"""
        try:
            # System metrics
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Bot metrics
            uptime = time.time() - self.start_time
            app = context.bot_data.get('application')
            active_tasks = len([t for t in asyncio.all_tasks() if not t.done()])
            
            # Get monitor status
            monitor = context.bot_data.get('monitor')
            monitor_status = "Stopped"
            if monitor:
                try:
                    monitor_status = "Running" if monitor.is_running() else "Stopped"
                except Exception:
                    # Fallback if is_running() fails
                    monitor_status = "Running" if getattr(monitor, 'running', False) else "Stopped"
            
            # Add connection status if available
            if monitor and hasattr(monitor, 'client') and monitor.client:
                monitor_status += f" ({'Connected' if monitor.client.is_connected() else 'Disconnected'})"
            
            message = (
                "🏥 𝗕𝗼𝘁 𝗛𝗲𝗮𝗹𝘁𝗵 𝗦𝘁𝗮𝘁𝘂𝘀:\n\n"
                "🖥️ 𝗦𝘆𝘀𝘁𝗲𝗺:\n"
                f"• 𝗖𝗣𝗨: {cpu}%\n"
                f"• 𝗠𝗲𝗺𝗼𝗿𝘆: {mem.percent}% ({mem.used/1024/1024:.1f}MB 𝘂𝘀𝗲𝗱)\n"
                f"• 𝗗𝗶𝘀𝗸: {disk.percent}% 𝗳𝗿𝗲𝗲\n\n"
                "🤖 𝗕𝗼𝘁:\n"
                f"• 𝗨𝗽𝘁𝗶𝗺𝗲: {uptime//3600}𝗵 {(uptime%3600)//60}𝗺\n"
                f"• 𝗠𝗲𝘀𝘀𝗮𝗴𝗲𝘀 𝗽𝗿𝗼𝗰𝗲𝘀𝘀𝗲𝗱: {self.message_count}\n"
                f"• 𝗔𝗰𝘁𝗶𝘃𝗲 𝘁𝗮𝘀𝗸𝘀: {active_tasks}\n"
                f"• 𝗨𝗽𝗱𝗮𝘁𝗲 𝗾𝘂𝗲𝘂𝗲: {app.update_queue.qsize() if app else 'N/A'}\n"
                f"• 𝗠𝗼𝗻𝗶𝘁𝗼𝗿 𝘀𝘁𝗮𝘁𝘂𝘀: {monitor_status}"
            )

            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            await update.message.reply_text(f"⚠️ Health check error: {e}")
            
    async def ping(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /ping command"""
        start = time.time()
        msg = await update.message.reply_text("🏓 Pong!")
        latency = (time.time() - start) * 1000
        await msg.edit_text(f"🏓 Pong! {latency:.0f}ms")
  
def get_maintenance_handlers():
    health_monitor = HealthMonitor()
    return [
        CommandHandler("restart", restart_bot),
        CommandHandler("shutdown", shutdown_bot),
        CommandHandler("reset", reset_json),
        CommandHandler("health", admin_only(health_monitor.health_check)),
        CommandHandler("ping", admin_only(health_monitor.ping))
    ]