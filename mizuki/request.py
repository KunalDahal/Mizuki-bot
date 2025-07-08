import os
import json
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from util import get_admin_ids,REQ_FILE,TARGET_FILE

async def request_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /request command from users with full validation"""
    if not context.args:
        await update.message.reply_text("Usage: /request <group_id>")
        return
    
    group_id = context.args[0].strip()
    user = update.effective_user
    
    try:
        group_id_int = int(group_id)
    except ValueError:
        await update.message.reply_text("❌ Invalid group ID. Must be a number")
        return
    
    try:
        try:
            chat = await context.bot.get_chat(group_id_int)
        except Exception as e:
            await update.message.reply_text(
                "❌ 𝗖𝗼𝘂𝗹𝗱𝗻'𝘁 𝗮𝗰𝗰𝗲𝘀𝘀 𝗴𝗿𝗼𝘂𝗽. 𝗣𝗹𝗲𝗮𝘀𝗲 𝗲𝗻𝘀𝘂𝗿𝗲:\n"
                "𝟭. 𝗜'𝗺 𝗮𝗱𝗱𝗲𝗱 𝘁𝗼 𝘁𝗵𝗲 𝗴𝗿𝗼𝘂𝗽\n"
                "𝟮. 𝗧𝗵𝗲 𝗴𝗿𝗼𝘂𝗽 𝗜𝗗 𝗶𝘀 𝗰𝗼𝗿𝗿𝗲𝗰𝘁\n"
                f"Error: {str(e)}"
            )
            return

        # 2. Check group type
        if chat.type == "private":
            await update.message.reply_text("❌ 𝗦𝗼𝗿𝗿𝘆, 𝗜 𝗱𝗼𝗻'𝘁 𝘄𝗼𝗿𝗸 𝘄𝗶𝘁𝗵 𝗽𝗿𝗶𝘃𝗮𝘁𝗲 𝗴𝗿𝗼𝘂𝗽𝘀")
            return
        
        # 3. Get member count
        try:
            member_count = await context.bot.get_chat_member_count(group_id_int)
        except Exception as e:
            await update.message.reply_text(f"❌ 𝗖𝗼𝘂𝗹𝗱𝗻'𝘁 𝗴𝗲𝘁 𝗺𝗲𝗺𝗯𝗲𝗿 𝗰𝗼𝘂𝗻𝘁: {str(e)}")
            return

        # 4. Check minimum members
        if member_count < 0:
            await update.message.reply_text("❌ 𝗚𝗿𝗼𝘂𝗽 𝗺𝘂𝘀𝘁 𝗵𝗮𝘃𝗲 𝗮𝘁 𝗹𝗲𝗮𝘀𝘁 𝟭,𝟬𝟬𝟬 𝗺𝗲𝗺𝗯𝗲𝗿𝘀")
            return

        # 5. Verify bot admin status
        try:
            bot_member = await context.bot.get_chat_member(group_id_int, context.bot.id)
            if bot_member.status not in ["administrator", "creator"]:
                await update.message.reply_text(
                    "❌ 𝗜 𝗻𝗲𝗲𝗱 𝘁𝗼 𝗯𝗲 𝗮𝗻 𝗮𝗱𝗺𝗶𝗻 𝘄𝗶𝘁𝗵:\n"
                    "- 𝗣𝗼𝘀𝘁 𝗠𝗲𝘀𝘀𝗮𝗴𝗲𝘀 𝗽𝗲𝗿𝗺𝗶𝘀𝘀𝗶𝗼𝗻\n"
                    "- 𝗥𝗲𝗮𝗱 𝗠𝗲𝘀𝘀𝗮𝗴𝗲𝘀 𝗽𝗲𝗿𝗺𝗶𝘀𝘀𝗶𝗼𝗻"
                )
                return
        except Exception as e:
            await update.message.reply_text(f"❌ 𝗖𝗼𝘂𝗹𝗱𝗻'𝘁 𝘃𝗲𝗿𝗶𝗳𝘆 𝗮𝗱𝗺𝗶𝗻 𝘀𝘁𝗮𝘁𝘂𝘀: {str(e)}")
            return

        # 6. Check if already approved
        with open(TARGET_FILE, 'r') as f:
            forward_list = json.load(f)
        
        if group_id_int in forward_list:
            await update.message.reply_text("✅ 𝗧𝗵𝗶𝘀 𝗴𝗿𝗼𝘂𝗽 𝗶𝘀 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗮𝗽𝗽𝗿𝗼𝘃𝗲𝗱!")
            return

        with open(REQ_FILE, 'r') as f:
            requests = json.load(f)
        
        if str(user.id) in requests:
            await update.message.reply_text("⚠️ 𝗬𝗼𝘂 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗵𝗮𝘃𝗲 𝗮 𝗽𝗲𝗻𝗱𝗶𝗻𝗴 𝗿𝗲𝗾𝘂𝗲𝘀𝘁")
            return

        requests[str(user.id)] = {
            "user_id": user.id,
            "username": user.username or user.first_name,
            "group_id": group_id_int,
            "group_title": chat.title,
            "member_count": member_count,
            "group_type": chat.type
        }
        
        with open(REQ_FILE, 'w') as f:
            json.dump(requests, f, indent=2)

        admins = get_admin_ids()
        notification_text = (
            f"📩 New Request:\n"
            f"👤 User: {user.mention_markdown()} (ID: {user.id})\n"
            f"👥 Group: {chat.title} (ID: {group_id_int})\n"
            f"🔢 Members: {member_count}\n"
            f"🔓 Type: {chat.type}\n\n"
            f"To approve: /approve {user.id}"
        )
        
        for admin_id in admins:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=notification_text,
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Failed to notify admin {admin_id}: {e}")

        await update.message.reply_text(
            "✅ 𝗥𝗲𝗾𝘂𝗲𝘀𝘁 𝘀𝗲𝗻𝘁 𝘁𝗼 𝗮𝗱𝗺𝗶𝗻𝘀!\n"
            "𝗬𝗼𝘂'𝗹𝗹 𝗯𝗲 𝗻𝗼𝘁𝗶𝗳𝗶𝗲𝗱 �𝗵𝗲𝗻 𝗮𝗽𝗽𝗿𝗼𝘃𝗲𝗱.",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ 𝗨𝗻𝗲𝘅𝗽𝗲𝗰𝘁𝗲𝗱 𝗲𝗿𝗿𝗼𝗿: {str(e)}")

def get_request_handler():
    return CommandHandler("request", request_command)