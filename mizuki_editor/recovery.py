import json
import logging
import os
from typing import Dict
from util import RECOVERY_FILE

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
                    self.last_message_ids = {int(k): v for k, v in json.load(f).items()}
                logger.info(f"Loaded recovery data for {len(self.last_message_ids)} channels")
        except Exception as e:
            logger.error(f"Error loading recovery data: {e}")
            self.last_message_ids = {}

    def save_recovery_data(self):
        """Save recovery data to JSON file"""
        try:
            with open(RECOVERY_FILE, 'w') as f:
                json.dump(self.last_message_ids, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving recovery data: {e}")

    def update_channel_state(self, channel_id: int, last_message_id: int):
        """Update the last processed message ID for a channel"""
        self.last_message_ids[channel_id] = last_message_id
        self.save_recovery_data()

    def get_last_message_id(self, channel_id: int) -> int:
        """Get last processed message ID for a channel"""
        return self.last_message_ids.get(channel_id, 0)

    async def initialize_channel_state(self, client, channel_id: int):
        """Initialize channel state if not in recovery file"""
        if channel_id not in self.last_message_ids:
            try:
                entity = await client.get_entity(channel_id)
                messages = await client.get_messages(entity, limit=1)
                if messages:
                    last_id = messages[0].id
                    self.update_channel_state(channel_id, last_id)
                    logger.info(f"Initialized channel {channel_id} with last ID: {last_id}")
                else:
                    self.update_channel_state(channel_id, 0)
                    logger.info(f"Initialized channel {channel_id} with last ID: 0 (no messages)")
            except Exception as e:
                logger.error(f"Error initializing channel {channel_id}: {e}")
                # Initialize with 0 if we can't access the channel
                self.update_channel_state(channel_id, 0)