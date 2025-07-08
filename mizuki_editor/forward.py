import logging
from telegram import InputMediaPhoto, InputMediaVideo
from telegram.constants import ParseMode
from typing import List, Dict
from util import get_target_channel

logger = logging.getLogger(__name__)

async def forward_to_all_targets(
    context, text: str = None, media: List[Dict] = None
):
    """Forward content to all target channels"""
    target_ids = get_target_channel()
    if not target_ids:
        logger.warning("No target channels configured")
        return

    for target_id in target_ids:
        try:
            if text:
                await context.bot.send_message(
                    chat_id=target_id, text=text, parse_mode=ParseMode.MARKDOWN_V2
                )
            elif media:
                if len(media) == 1:
                    item = media[0]
                    caption = item.get("processed_caption")
                    parse_mode = ParseMode.MARKDOWN_V2 if caption else None

                    if item["type"] == "photo":
                        await context.bot.send_photo(
                            chat_id=target_id,
                            photo=item["file_id"],
                            caption=caption,
                            parse_mode=parse_mode,
                        )
                    elif item["type"] in ["video", "document"]:
                        await context.bot.send_video(
                            chat_id=target_id,
                            video=item["file_id"],
                            caption=caption,
                            parse_mode=parse_mode,
                        )
                else:
                    media_group = []
                    for i, item in enumerate(media):
                        if item["type"] == "photo":
                            media_type = InputMediaPhoto
                        elif item["type"] in ["video", "document"]:
                            media_type = InputMediaVideo
                        else:
                            continue
                        caption = item.get("processed_caption") if i == 0 else None
                        parse_mode = ParseMode.MARKDOWN_V2 if caption else None

                        media_group.append(
                            media_type(
                                media=item["file_id"],
                                caption=caption,
                                parse_mode=parse_mode,
                            )
                        )

                    await context.bot.send_media_group(
                        chat_id=target_id, media=media_group
                    )
        except Exception as e:
            logger.error(f"Failed to forward to channel {target_id}: {e}")