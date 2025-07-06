import hashlib
import os
import json
import time
import logging
from moviepy import VideoFileClip
from PIL import Image
from typing import List,Dict
import imagehash
import io
from telegram import Message
from util import MAX_HASH_ENTRIES, HASH_FILE

logger = logging.getLogger(__name__)

def compute_video_hashes(video_path: str) -> Dict[str, str]:
    """
    Compute MD5 and SHA256 hashes of video frames (first 10 seconds at 2 FPS).
    Returns a dictionary with 'md5' and 'sha256' hex digests.
    """
    try:
        clip = VideoFileClip(video_path)
        end_time = min(10, clip.duration)

        md5_hash = hashlib.md5()
        sha256_hash = hashlib.sha256()

        for time, img in clip.iter_frames(fps=2, with_times=True):
            if time > end_time:
                break

            frame_bytes = img.tobytes()
            md5_hash.update(frame_bytes)
            sha256_hash.update(frame_bytes)

        clip.close()
        return {
            'md5': md5_hash.hexdigest(),
            'sha256': sha256_hash.hexdigest()
        }

    except Exception as e:
        logger.error(f"Error computing video hashes: {e}")
        return {'md5': '', 'sha256': ''}


def _load_hash_data():
    """Load hash data from JSON file"""
    hash_data = {}
    try:
        if os.path.exists(HASH_FILE):
            with open(HASH_FILE, 'r') as f:
                hash_data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading hash data: {e}")
    return hash_data

def _save_hash_data(hash_data):
    """Save hash data to JSON file"""
    try:
        with open(HASH_FILE, 'w') as f:
            json.dump(hash_data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving hash data: {e}")

async def _generate_media_hashes(message: Message) -> List[Dict]:
    """Generate hashes for media content with 20MB size limit"""
    media_hashes = []
    
    if message.photo:
        try:
            largest_photo = message.photo[-1]
            file = await largest_photo.get_file()
            
            # Updated to 20MB limit (Telegram Bot API limit)
            if file.file_size and file.file_size > 20_000_000:
                logger.warning(f"Skipping large photo ({file.file_size/1_000_000:.1f}MB)")
                return media_hashes
                
            file_bytes = await file.download_as_bytearray()
            
            image = Image.open(io.BytesIO(file_bytes))
            media_hashes.append({
                'type': 'photo',
                'phash': str(imagehash.phash(image)),
                'sha256': hashlib.sha256(file_bytes).hexdigest(),
                'md5': hashlib.md5(file_bytes).hexdigest(),
                'file_id': largest_photo.file_id
            })
        except Exception as e:
            logger.error(f"Error processing photo: {e}")
    
    elif message.video:
        try:
            video = message.video
            file = await video.get_file()
            
            # Updated to 20MB limit (Telegram Bot API limit)
            if file.file_size and file.file_size > 20_000_000:
                logger.warning(f"Skipping large video ({file.file_size/1_000_000:.1f}MB)")
                return media_hashes
                
            # Download entire video at once (simpler but uses more memory)
            file_bytes = await file.download_as_bytearray()
            
            media_hashes.append({
                'type': 'video',
                'sha256': hashlib.sha256(file_bytes).hexdigest(),
                'md5': hashlib.md5(file_bytes).hexdigest(),
                'file_id': video.file_id
            })
        except Exception as e:
            logger.error(f"Error processing video: {e}")
    
    return media_hashes

async def _add_to_hash_data(hash_data, caption: str, media_hashes: List[Dict]):
    """Add new media hashes to the hash database"""
    try:
        if len(hash_data) >= MAX_HASH_ENTRIES:
            oldest_key = next(iter(hash_data))
            hash_data.pop(oldest_key)
            logger.info(f"Removed oldest hash entry to maintain size limit")
        
        new_key = hashlib.md5(caption.encode()).hexdigest() if caption else media_hashes[0]['sha256']
        hash_data[new_key] = {
            'caption': caption,
            'media': media_hashes,
            'timestamp': int(time.time())
        }
        _save_hash_data(hash_data)
    except Exception as e:
        logger.error(f"Error adding to hash data: {e}")