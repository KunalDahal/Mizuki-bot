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

        for t, img in clip.iter_frames(fps=2, with_times=True):
            if t > end_time:
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
    FILE_SIZE_LIMIT = 20_000_000  # 20MB
    
    if message.photo:
        try:
            largest_photo = message.photo[-1]
            try:
                file = await largest_photo.get_file()
            except Exception as e:
                if "too big" in str(e).lower():
                    logger.warning("Skipping large photo (over 20MB)")
                    return [{'type': 'photo', 'skipped': True, 'file_id': largest_photo.file_id}]
                raise

            if file.file_size and file.file_size > FILE_SIZE_LIMIT:
                logger.warning(f"Skipping large photo ({file.file_size/1_000_000:.1f}MB)")
                return [{'type': 'photo', 'skipped': True, 'file_id': largest_photo.file_id}]
                
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
            try:
                file = await video.get_file()
            except Exception as e:
                if "too big" in str(e).lower():
                    logger.warning("Skipping large video (over 20MB)")
                    return [{'type': 'video', 'skipped': True, 'file_id': video.file_id}]
                raise

            if file.file_size and file.file_size > FILE_SIZE_LIMIT:
                logger.warning(f"Skipping large video ({file.file_size/1_000_000:.1f}MB)")
                return [{'type': 'video', 'skipped': True, 'file_id': video.file_id}]
                
            # Download entire video at once
            file_path = await file.download_to_drive()
            
            # Compute video hashes
            video_hashes = compute_video_hashes(file_path)
            
            media_hashes.append({
                'type': 'video',
                'sha256': video_hashes['sha256'],
                'md5': video_hashes['md5'],
                'file_id': video.file_id
            })
            
            # Clean up temporary file
            os.remove(file_path)
        except Exception as e:
            logger.error(f"Error processing video: {e}")
    
    return media_hashes

async def _add_to_hash_data(hash_data, caption: str, media_hashes: List[Dict]):
    """Add new media hashes to the hash database"""
    try:
        # Generate unique key using media hash instead of caption
        media_keys = []
        for media in media_hashes:
            # Skip skipped media (large files)
            if media.get('skipped'):
                continue
                
            if media['type'] == 'photo':
                key = media['phash']
            else:
                key = media['sha256']

            media_keys.append(key)
            hash_data[key] = {
                'caption': caption,
                'media': media,
                'timestamp': int(time.time())
            }
        
        # Maintain size limit
        while len(hash_data) > MAX_HASH_ENTRIES:
            oldest_key = min(hash_data, key=lambda k: hash_data[k]['timestamp'])
            hash_data.pop(oldest_key)
            logger.info(f"Removed oldest hash entry to maintain size limit")
        
        _save_hash_data(hash_data)
    except Exception as e:
        logger.error(f"Error adding to hash data: {e}")