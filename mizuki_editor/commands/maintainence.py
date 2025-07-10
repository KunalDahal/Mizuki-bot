import os
import sys
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from mizuki_editor.commands.admin import admin_only
import logging
from util import JSON_FOLDER, SOURCE_FILE, REMOVE_FILE, REPLACE_FILE, BAN_FILE, HASH_FILE, SYMBOL_FILE, EMOJI_FILE, TARGET_FILE, RECOVERY_FILE
import psutil
import time
import asyncio
import json

logger = logging.getLogger(__name__)

DEFAULT_STRUCTURES = {
    "channels": [],
    "remove": [],
    "replace": {},
    "banned": [],
    "hash": {},
    "symbol": [],
    "emoji": {},
    "requests": {},
    "target": [],
    "recovery": {}
}

FILE_MAPPING = {
    "channels": SOURCE_FILE,
    "remove": REMOVE_FILE,
    "replace": REPLACE_FILE,
    "banned": BAN_FILE,
    "hash": HASH_FILE,
    "symbol": SYMBOL_FILE,
    "emoji": EMOJI_FILE,
    "target": TARGET_FILE,
    "recovery": RECOVERY_FILE
}

@admin_only
async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /restart command"""
    await update.message.reply_text("🔄 Restarting bot...")
    logger.info("Restart initiated by admin")

    if 'application' in context.bot_data:
        await context.bot_data['application'].stop()

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
async def reset_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all available JSON files that can be reset"""
    message = "📁 Available JSON files to reset:\n\n"
    for file_name in sorted(FILE_MAPPING.keys()):
        message += f"• {file_name}\n"
    
    message += "\nUse /reset <file_name> to reset a specific file\n"
    message += "Use /reset to reset all files"
    
    await update.message.reply_text(message)

@admin_only
async def reset_json(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for reset commands"""
    if not context.args:
        try:
            reset_count = 0
            for file_name, file_path in FILE_MAPPING.items():
                try:
                    with open(file_path, 'w') as f:
                        json.dump(DEFAULT_STRUCTURES[file_name], f, indent=2)
                    reset_count += 1
                except Exception as e:
                    logger.error(f"Error resetting {file_name}: {e}")
                    continue
            
            await update.message.reply_text(f"✅ Reset {reset_count}/{len(FILE_MAPPING)} JSON files to default")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error during full reset: {e}")
    else:
        file_name = context.args[0].lower()
        if file_name not in FILE_MAPPING:
            await update.message.reply_text(f"⚠️ Unknown file: {file_name}\nUse /reset_show to see available files")
            return
        
        try:
            with open(FILE_MAPPING[file_name], 'w') as f:
                json.dump(DEFAULT_STRUCTURES[file_name], f, indent=2)
            await update.message.reply_text(f"✅ Reset {file_name} file to default")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error resetting {file_name}: {e}")

class HealthMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.message_count = 0

    async def health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /health command"""
        try:
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            uptime = time.time() - self.start_time
            app = context.bot_data.get('application')
            active_tasks = len([t for t in asyncio.all_tasks() if not t.done()])
        
            monitor = context.bot_data.get('monitor')
            monitor_status = "Stopped"
            if monitor:
                try:
                    monitor_status = "Running" if monitor.is_running() else "Stopped"
                except Exception:
                    monitor_status = "Running" if getattr(monitor, 'running', False) else "Stopped"
            
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
        CommandHandler("reset_show", reset_show),
        CommandHandler("health", admin_only(health_monitor.health_check)),
        CommandHandler("ping", admin_only(health_monitor.ping))
    ]