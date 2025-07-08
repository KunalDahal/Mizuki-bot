import os
import json
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from util import get_admin_ids,JSON_FOLDER,REQ_FILE,TARGET_FILE

async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admins = get_admin_ids()
    if user.id not in admins:
        await update.message.reply_text("❌ You don't have permission to approve requests")
        return

    if not context.args:
        await update.message.reply_text("Usage: /approve <user_id>")
        return
    
    user_id = context.args[0].strip()
    
    try:

        with open(REQ_FILE, 'r') as f:
            requests = json.load(f)
        
        if user_id not in requests:
            await update.message.reply_text(f"❌ No pending request found for user {user_id}")
            return
        
        group_id = requests[user_id]["group_id"]

        with open(TARGET_FILE, 'r') as f:
            forward_list = json.load(f)
        
        if group_id not in forward_list:
            forward_list.append(group_id)
            with open(TARGET_FILE, 'w') as f:
                json.dump(forward_list, f, indent=2)
        
        del requests[user_id]
        with open(REQ_FILE, 'w') as f:
            json.dump(requests, f, indent=2)
        
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=f"🎉 𝗬𝗼𝘂𝗿 𝗿𝗲𝗾𝘂𝗲𝘀𝘁 𝗳𝗼𝗿 𝗴𝗿𝗼𝘂𝗽 {group_id} 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗮𝗽𝗽𝗿𝗼𝘃𝗲𝗱!"
            )
        except Exception as e:
            print(f"Couldn't notify user {user_id}: {e}")
        
        await update.message.reply_text(
            f"✅ Approved request from user {user_id}\n"
            f"Group {group_id} added to forwarding list"
        )
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error processing approval: {str(e)}")

def get_approve_handler():
    return CommandHandler("approve", approve_command)