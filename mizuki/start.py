from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from util import load_users, save_users

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command and store user ID"""
    user = update.effective_user
    
    users = load_users()
    
    if str(user.id) not in users:
        users.append(str(user.id))
        save_users(users)
        message = (
            "✦ 𝗠𝗶𝘇𝘂𝗸𝗶 𝗕𝗼𝘁 𝗮𝘁 𝘆𝗼𝘂𝗿 𝘀𝗲𝗿𝘃𝗶𝗰𝗲! ✦\n\n"
            "I 𝗮𝗺 𝘁𝗵𝗲 𝗽𝗿𝗼𝘂𝗱 𝗯𝗼𝘁 𝗼𝗳 𝘁𝗵𝗲 𝗔𝗻𝗶𝗺𝗲 𝗢𝗰𝗲𝗮𝗻 𝗰𝗼𝗺𝗺𝘂𝗻𝗶𝘁𝘆.\n"
            "𝗠𝘆 𝗺𝗮𝗶𝗻 𝗱𝘂𝘁𝘆 𝗶𝘀 𝘁𝗼 𝗸𝗲𝗲𝗽 𝘁𝗵𝗲 𝗰𝗵𝗮𝗻𝗻𝗲𝗹 ⟪ @Animes_News_Ocean ⟫ 𝗳𝗶𝗹𝗹𝗲𝗱 𝘄𝗶𝘁𝗵 𝗳𝗿𝗲𝘀𝗵 𝗮𝗻𝗶𝗺𝗲, 𝗺𝗮𝗻𝗴𝗮, 𝗺𝗮𝗻𝗵𝘄𝗮 𝗮𝗻𝗱 𝗹𝗶𝗴𝗵𝘁 𝗻𝗼𝘃𝗲𝗹 𝗻𝗲𝘄𝘀!\n\n"
            "⋆ 𝗥𝗶𝗴𝗵𝘁 𝗻𝗼𝘄, 𝗜 𝗳𝗼𝗿𝘄𝗮𝗿𝗱 𝗮𝗹𝗹 𝘁𝗵𝗲 𝗹𝗮𝘁𝗲𝘀𝘁 𝘂𝗽𝗱𝗮𝘁𝗲𝘀 𝘀𝘁𝗿𝗮𝗶𝗴𝗵𝘁 𝘁𝗵𝗲𝗿𝗲.\n"
            "𝗕𝘂𝘁 𝗵𝗲𝘆, 𝗜 𝘄𝗮𝗻𝘁 𝘆𝗼𝘂𝗿 𝗼𝗽𝗶𝗻𝗶𝗼𝗻!\n"
            "𝗦𝗵𝗼𝘂𝗹𝗱 𝗜 𝗮𝗹𝘀𝗼 𝗳𝗼𝗿𝘄𝗮𝗿𝗱 𝗻𝗲𝘄𝘀 𝗱𝗶𝗿𝗲𝗰𝘁𝗹𝘆 𝗶𝗻𝘁𝗼 𝘆𝗼𝘂𝗿 𝗴𝗿𝗼𝘂𝗽𝘀?\n\n"
            "𝗜𝗳 𝘆𝗲𝘀, 𝗽𝗹𝗲𝗮𝘀𝗲 𝘂𝘀𝗲 𝘁𝗵𝗲 /upvote 𝗰𝗼𝗺𝗺𝗮𝗻𝗱!\n"
            "𝗢𝗻𝗰𝗲 𝗜 𝗿𝗲𝗮𝗰𝗵 𝟭𝗞 𝘂𝗽𝘃𝗼𝘁𝗲𝘀, 𝗜 𝘄𝗶𝗹𝗹 𝗴𝗲𝘁 𝗮 𝗺𝗮𝗷𝗼𝗿 𝘂𝗽𝗴𝗿𝗮𝗱𝗲 𝗮𝗻𝗱 𝗯𝗲 𝗮𝗯𝗹𝗲 𝘁𝗼 𝗳𝗼𝗿𝘄𝗮𝗿𝗱 𝗻𝗲𝘄𝘀 𝗱𝗶𝗿𝗲𝗰𝘁𝗹𝘆 𝗶𝗻𝘁𝗼 𝘆𝗼𝘂𝗿 𝗴𝗿𝗼𝘂𝗽𝘀 𝘁𝗼𝗼!\n\n"
            "➤ 𝗗𝗼𝗻’𝘁 𝘄𝗼𝗿𝗿𝘆, 𝗜’𝗹𝗹 𝗶𝗻𝗳𝗼𝗿𝗺 𝘆𝗼𝘂 𝗼𝗻𝗰𝗲 𝘁𝗵𝗲 𝗻𝗲𝘄 𝘃𝗲𝗿𝘀𝗶𝗼𝗻 𝗶𝘀 𝗿𝗲𝗮𝗱𝘆.\n\n"
            "☆ 𝗧𝗵𝗮𝗻𝗸𝘀 𝗳𝗼𝗿 𝗯𝗲𝗶𝗻𝗴 𝗵𝗲𝗿𝗲. 𝗦𝘁𝗮𝘆 𝘁𝘂𝗻𝗲𝗱, 𝗲𝘅𝗰𝗶𝘁𝗶𝗻𝗴 𝘁𝗶𝗺𝗲𝘀 𝗮𝗵𝗲𝗮𝗱!\n\n"
            "𝗡𝗲𝗲𝗱 𝘀𝘂𝗽𝗽𝗼𝗿𝘁? 𝗖𝗼𝗻𝘁𝗮𝗰𝘁: @suu_111"
        )
    
    await update.message.reply_text(message)

def get_start_handler():
    return CommandHandler("start", start_command)