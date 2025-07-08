import json
import logging
import os
from typing import Dict, Optional
from telethon import TelegramClient
from telethon.tl.types import MessageService
from telethon.errors import ChannelPrivateError
from util import RECOVERY_FILE, get_target_channel

logger = logging.getLogger(__name__)

class RecoverySystem:
    def __init__(self):
        self.last_message_ids: Dict[int, int] = {}
        self._load_recovery_data()

    def _load_recovery_data(self):
        """Load recovery data from JSON file"""
        try:
            if os.path.exists(RECOVERY_FILE):
                with open(RECOVERY_FILE, 'r') as f:
                    data = json.load(f)
                 
                    self.last_message_ids = {int(k): v for k, v in data.items()}
                logger.info(f"Loaded recovery data for {len(self.last_message_ids)} channels")
        except Exception as e:
            logger.error(f"Error loading recovery data: {e}")
            self.last_message_ids = {}

    def save_recovery_data(self):
        """Save recovery data to JSON file"""
        try:
            with open(RECOVERY_FILE, 'w') as f:
                json.dump(self.last_message_ids, f, indent=2)
            logger.debug("Recovery data saved successfully")
        except Exception as e:
            logger.error(f"Error saving recovery data: {e}")

    def update_channel_state(self, channel_id: int, last_message_id: int):
        """Update the last processed message ID for a channel"""
        current_last = self.last_message_ids.get(channel_id, 0)
        
        if last_message_id > current_last:
            self.last_message_ids[channel_id] = last_message_id
            self.save_recovery_data()
            logger.debug(f"Updated channel {channel_id} to last ID: {last_message_id}")

    def get_last_message_id(self, channel_id: int) -> int:
        """Get last processed message ID for a channel"""
        return self.last_message_ids.get(channel_id, 0)

    async def initialize_channel_state(self, client: TelegramClient, channel_id: int):
        """Initialize channel state if not in recovery file"""
        if channel_id not in self.last_message_ids:
            try:
                entity = await client.get_entity(channel_id)
                
                messages = await client.get_messages(
                    entity, 
                    limit=10,
                    reverse=True  
                )
                
                if messages:
                 
                    valid_messages = [msg for msg in messages if not isinstance(msg, MessageService)]
                    
                    if valid_messages:
                        last_id = max(msg.id for msg in valid_messages)
                        self.update_channel_state(channel_id, last_id)
                        logger.info(f"Initialized channel {channel_id} with last ID: {last_id}")
                    else:
                        self.update_channel_state(channel_id, 0)
                        logger.info(f"Initialized channel {channel_id} with last ID: 0 (no valid messages)")
                else:
                    self.update_channel_state(channel_id, 0)
                    logger.info(f"Initialized channel {channel_id} with last ID: 0 (no messages)")
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid channel ID format: {channel_id} - {e}")
                self.update_channel_state(channel_id, 0)
            except ChannelPrivateError:
                logger.error(f"Bot has no access to channel {channel_id}")
                self.update_channel_state(channel_id, 0)
            except Exception as e:
                logger.error(f"Error initializing channel {channel_id}: {e}")
    
                self.update_channel_state(channel_id, 0)

    async def recover_channels(self, client: TelegramClient):
        """Recover all channels by reinitializing their states"""
        logger.info("Starting channel recovery process")
 
        target_channels = get_target_channel()
        if not target_channels:
            logger.warning("No target channels configured for recovery")
            return
            
        for channel_id in target_channels:
            try:
            
                await self.initialize_channel_state(client, channel_id)
                
                current_id = self.get_last_message_id(channel_id)
                logger.info(f"Recovered channel {channel_id} with last ID: {current_id}")
            except Exception as e:
                logger.error(f"Failed to recover channel {channel_id}: {e}")
        
        logger.info("Channel recovery completed")

    def get_channel_states(self) -> Dict[int, int]:
        """Get all channel states as a dictionary"""
        return self.last_message_ids.copy()

    def remove_channel(self, channel_id: int):
        """Remove a channel from recovery tracking"""
        if channel_id in self.last_message_ids:
            del self.last_message_ids[channel_id]
            self.save_recovery_data()
            logger.info(f"Removed channel {channel_id} from recovery tracking")

    def clear_all_states(self):
        """Clear all recovery states (for debugging)"""
        self.last_message_ids = {}
        self.save_recovery_data()
        logger.warning("Cleared all recovery states")

    def find_most_active_channel(self) -> Optional[int]:
        """Find the channel with the highest last message ID"""
        if not self.last_message_ids:
            return None
            
        max_id = 0
        max_channel = None
        for channel_id, last_id in self.last_message_ids.items():
            if last_id > max_id:
                max_id = last_id
                max_channel = channel_id
                
        return max_channel

    def get_channel_progress(self, channel_id: int) -> str:
        """Get human-readable progress for a channel"""
        last_id = self.get_last_message_id(channel_id)
        return f"Channel {channel_id} - Last processed ID: {last_id}"