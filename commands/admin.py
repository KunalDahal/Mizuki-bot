from telegram import Update
from telegram.ext import ContextTypes
from functools import wraps
from util import get_admin_ids

def admin_only(func):
    """Decorator to restrict command access to admins only"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        admins = get_admin_ids()
        
        if user_id not in admins:
            await update.message.reply_text("⛔ Unauthorized: You don't have permission to use this command")
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapper