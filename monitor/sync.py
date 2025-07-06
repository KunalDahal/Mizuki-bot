from util import RECOVERY_FILE,load_channels
import json 
import logging
import asyncio

logger=logging.getLogger(__name__)

async def sync_channel_files():
    """Ensure source_id.json and last_message_id.json stay synchronized"""
    while True:
        try:
            # Load current channel lists
            source_channels = set(load_channels())
            with open(RECOVERY_FILE, 'r') as f:
                recovery_data = json.load(f)
            recovery_channels = set(map(int, recovery_data.keys()))
            
            # Find differences
            added = source_channels - recovery_channels
            removed = recovery_channels - source_channels
            
            # Update recovery file if needed
            if added or removed:
                logger.info(f"Syncing channel files - Added: {added}, Removed: {removed}")
                for channel in added:
                    recovery_data[str(channel)] = 0
                for channel in removed:
                    recovery_data.pop(str(channel), None)
                
                with open(RECOVERY_FILE, 'w') as f:
                    json.dump(recovery_data, f, indent=2)
            
            await asyncio.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Error syncing channel files: {e}")
            await asyncio.sleep(30)