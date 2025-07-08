from telegram import Update
import functools 
import logging
from util import get_admin_ids

logger = logging.getLogger(__name__)

def admin_only(func):
    @functools.wraps(func)
    async def wrapper(update_or_self, context):
        if isinstance(update_or_self, Update):
            update = update_or_self
        else:
            update = context.args[0] if context.args else None
        
        if not update or not update.effective_user:
            logger.warning("No effective user in update")
            return
        
        user_id = update.effective_user.id
        if user_id not in get_admin_ids():
            await update.message.reply_text("🚫 You are not authorized to use this command.")
            return

        if isinstance(update_or_self, Update):
            return await func(update, context)
        else:
            return await func(update_or_self, update, context)
    
    return wrapper