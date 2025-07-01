from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Bot
from telegram.ext import ConversationHandler, CallbackContext
from storage.config import OWNER_ID, BOT_TOKEN, load_subscriptions, save_subscriptions,SUBSCRIPTION_DAYS
import logging
from datetime import datetime, timedelta,date
from commands.command_lock import acquire_lock,release_lock

logger = logging.getLogger(__name__)
bot = Bot(BOT_TOKEN)
GET_CHANNELS = "GET_CHANNELS"
GET_USERNAME = "GET_USERNAME"
PAYMENT_PROOF = "PAYMENT_PROOF"
subs = {} 

def check_subscription(user_id: str):
    subs = load_subscriptions()
    user_data = subs.get(str(user_id), {})
    if not user_data.get('subscribed'):
        return False
    expiry_date = date.fromisoformat(user_data['expiry_date'])
    return date.today() < expiry_date

async def subscribe_start(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    if not acquire_lock(user_id, "subscribe"):
        await update.message.reply_text(  
            "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"  
            "⚠️ *Gomenasai!* A spell is already active! 🏃♂️\n"  
            "▹ Finish your *current task* before new magic! ✨\n"
            "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n" ,  
            parse_mode='Markdown'  
        )  
        return ConversationHandler.END
    await update.message.reply_text(  
        "🌸━━━ *𝑺𝑼𝑩𝑺𝑪𝑹𝑰𝑷𝑻𝑰𝑶𝑵 桜* ━━━🌸\n"  
        "▰▰▰▰▰▰▰▰▰▰▰▰▰\n"  
        "🎌 *𝑩𝑨𝑺𝑰𝑪* » `₹299`\n"  
        "   ✧ 𝑭𝒖𝒍𝒍 𝒂𝒄𝒄𝒆𝒔𝒔 𝒕𝒐 𝒑𝒓𝒆𝒎𝒊𝒖𝒎 𝒇𝒆𝒂𝒕𝒖𝒓𝒆𝒔 🗝️✨\n\n"  
        "🎏 *𝑺𝑬𝑵𝑫 𝑪𝑯𝑨𝑵𝑵𝑬𝑳 𝑰𝑫𝒔* » \n"  
        "`(𝑪𝒐𝒎𝒎𝒂-𝒔𝒆𝒑𝒂𝒓𝒂𝒕𝒆𝒅)`\n"
        "▰▰▰▰▰▰▰▰▰▰▰▰▰\n",  
        parse_mode='Markdown'  
    )  
    return GET_CHANNELS

async def get_channels(update: Update, context: CallbackContext):
    user = update.message.from_user
    user_id = str(user.id)
    channel_ids = [ch.strip() for ch in update.message.text.split(",") if ch.strip()]
    
    subs = load_subscriptions()  # RELOAD FRESH DATA
    
    # Case 1: User exists + subscribed + channel conflict
    if str(user.id) in subs and check_subscription(str(user.id)):
        user_subscription = subs[str(user.id)]
        existing_channels = user_subscription.get("ch_id", [])
        
        # Check if ANY new channel exists in user's own list
        if any(ch in existing_channels for ch in channel_ids):
            await update.message.reply_text(
                "▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
                f"⚠️ *Mou!* This channel already belongs to YOU! 🏮\n"
                "`💡 Try a never-before-used channel ID!`/n"
                "▰▰▰▰▰▰▰▰▰▰▰▰▰\n",
                parse_mode='Markdown'
            )
            release_lock(user_id)
            return ConversationHandler.END

        # Check if ANY new channel exists in OTHER users' lists
        for uid, sub in subs.items():
            if uid != str(user.id) and any(ch in sub.get("ch_id", []) for ch in channel_ids):
                other_username = sub.get("username", "a mystery user")
                await update.message.reply_text(
                    "▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
                    f"✦ Already claimed by *@{other_username}* 🎎\n"
                    "✦ 𝑻𝒓𝒚 𝒂 𝒏𝒆𝒘 𝑰𝑫 𝒐𝒓 𝒏𝒆𝒈𝒐𝒕𝒊𝒂𝒕𝒆 𝒘𝒊𝒕𝒉 𝒕𝒉𝒆𝒎! 🏮\n"
                    "▰▰▰▰▰▰▰▰▰▰▰▰▰\n",
                    parse_mode='Markdown'
                )
                release_lock(user_id)
                return ConversationHandler.END
                
    # Case 2: New subscription
    context.user_data["ch_id"] = channel_ids
    await update.message.reply_text(
        "▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        "✅ *Yatta!* Channels secured in *enchanted scroll* 📜\n\n"
        "🎐 *𝑵𝑬𝑿𝑻 𝑺𝑻𝑬𝑷* » Enter your *payment UPI username* 💳\n"
        "▰▰▰▰▰▰▰▰▰▰▰▰▰\n",
        parse_mode='Markdown'
    )
    return GET_USERNAME

async def get_username(update: Update, context: CallbackContext):
    username = update.message.text.strip()
    context.user_data["payment_username"] = username
    await update.message.reply_text(  
        "💸 *𝑷𝑨𝒀𝑴𝑬𝑵𝑻 𝑺𝑻𝑬𝑷𝑺* 💸\n"  
        "▰▰▰▰▰▰▰▰▰▰▰▰▰\n"  
        "1️⃣ » 💳 𝑺𝒆𝒏𝒅 `₹299` 𝒕𝒐 » `kunaldahal123@oksbi`\n"  
        "2️⃣ » 📝 𝑷𝑨𝒀𝑴𝑬𝑵𝑻 𝑵𝑶𝑻𝑬: 𝑨𝒅𝒅 𝒀𝑶𝑼𝑹 𝑼𝑺𝑬𝑹𝑵𝑨𝑴𝑬!\n\n"  
        "📸 *𝑻𝑯𝑬𝑵* » 𝑺𝒆𝒏𝒅 𝒑𝒂𝒚𝒎𝒆𝒏𝒕 𝒔𝒄𝒓𝒆𝒆𝒏𝒔𝒉𝒐𝒕! 🖼️\n"  
        "`(𝑶𝒓 'cancel' 𝒕𝒐 𝒆𝒙𝒊𝒕)`\n"
        "▰▰▰▰▰▰▰▰▰▰▰▰▰\n",  
        parse_mode='Markdown'  
    )  
    return PAYMENT_PROOF

async def payment_proof(update: Update, context):
    user = update.effective_user
    key = str(user.id)
    user_id = str(update.message.from_user.id)
    
    # Check if the user typed "cancel" (in any case)
    if update.message.text and update.message.text.lower() == "cancel":
        await update.message.reply_text(  
            "▰▰▰▰▰▰▰▰▰▰▰▰▰\n"  
            "❌ Subscription request *vanished*! 🌫️\n"  
            "▹ Your *omamori* fades to stardust... 💮\n\n"  
            "`🏮 Return with /subscribe`\n"
            "▰▰▰▰▰▰▰▰▰▰▰▰▰\n" ,  
            parse_mode='Markdown'  
        )  
        release_lock(user_id)
        return ConversationHandler.END

    # Only allow photos. If no photo is attached, ask the user to send a photo.
    if not update.message.photo:
        await update.message.reply_text(
            "▰▰▰▰▰▰▰▰▰▰▰▰▰\n"  
            "⚠️ *Only* Payment *photos* allowed! 🌕\n"  
            "▹ Send a *screenshot* 🖼️ or type `cancel` 🚫\n"
            "▰▰▰▰▰▰▰▰▰▰▰▰▰\n" ,  
            parse_mode='Markdown'  
        )  
        # Return the same state to keep waiting for the correct input.
        return PAYMENT_PROOF

    channels = context.user_data.get("ch_id", []) 
    payment_username = context.user_data.get("payment_username", "")

    subs = load_subscriptions()
    key = str(user.id)
    subs[key] = {
        "username": user.username,
        "user-id": user.id,
        "ch_id": channels,
        "subscribed": False,
        "payment_username": payment_username,
        "Active": False
    }
    save_subscriptions(subs)

    request_text = (
        "🆕 Subscription Request 🆕\n"
        f"User: @{user.username}\n"
        f"User ID: {user.id}\n"
        f"Channels: {', '.join(channels)}\n"
        f"Payment username: {payment_username}"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Approve", callback_data=f"approve_{key}"),
            InlineKeyboardButton("Reject", callback_data=f"reject_{key}")
        ]
    ])

    photo_file = update.message.photo[-1].file_id
    await context.bot.send_photo(
        chat_id=OWNER_ID,
        photo=photo_file,
        caption=request_text,
        reply_markup=keyboard
    )
    
    await update.message.reply_text(  
        "▰▰▰▰▰▰▰▰▰▰▰▰▰\n" 
        "🕊️ 𝑹𝒆𝒗𝒊𝒆𝒘 𝒊𝒏 𝒑𝒓𝒐𝒈𝒓𝒆𝒔𝒔... ⌛\n"  
        "✦ 𝑾𝒂𝒊𝒕 𝒘𝒂𝒓𝒎𝒍𝒚, 𝒏𝒆? ☕\n"
        "▰▰▰▰▰▰▰▰▰▰▰▰▰\n",  
        parse_mode='Markdown'  
    )  
    release_lock(user_id)
    return ConversationHandler.END

async def cancel_subscription(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    release_lock(user_id)
    await update.message.reply_text(   
        "▰▰▰▰▰▰▰▰▰▰▰▰▰\n"  
        "❌ 𝑺𝒖𝒃𝒔𝒄𝒓𝒊𝒑𝒕𝒊𝒐𝒏 𝒄𝒂𝒏𝒄𝒆𝒍𝒍𝒆𝒅!\n"  
        "`𝑼𝒔𝒆 /𝒔𝒖𝒃𝒔𝒄𝒓𝒊𝒃𝒆 𝒕𝒐 𝒓𝒆𝒕𝒖𝒓𝒏` 🌸\n"
        "▰▰▰▰▰▰▰▰▰▰▰▰▰\n",  
        parse_mode='Markdown'  
    )  
    return ConversationHandler.END

async def handle_subscription_callback(update: Update, context: CallbackContext):  
    query = update.callback_query  
    await query.answer("🌀 *Processing...* ✨")  # Stylized answer  

    data = query.data  
    key = data.split("_", 1)[1]  

    subs = load_subscriptions()  
    user_id = str(update.effective_user.id)  

    if key not in subs:  
        await query.edit_message_text(  
            text=(   
                "▰▰▰▰▰▰▰▰▰▰▰▰▰\n"  
                "⛩️ *Gomenasai!* This subscription dissolved like morning mist 🌫️\n"  
                "`🔍 Key not found in sacred scrolls`\n"  
                "▰▰▰▰▰▰▰▰▰▰▰▰▰\n" 
            ),  
            parse_mode='Markdown'  
        )  
        release_lock(user_id)  
        return  

    if data.startswith("approve_"):  
        await approve_subscription(key)  
        await query.edit_message_text(  
            text=(  
                "▰▰▰▰▰▰▰▰▰▰▰▰▰\n"  
                "🌸 *Yatta!* Subscription blessed by shrine maidens 🏮\n"  
                "▹ User now wields *premium omamori* 🗝️✨\n"  
                "▰▰▰▰▰▰▰▰▰▰▰▰▰\n" 
            ),  
            parse_mode='Markdown'  
        )  
    elif data.startswith("reject_"):  
        await reject_subscription(key)  
        await query.edit_message_text(  
            text=(  
                "▄▄▄▄▄▄▄▄▄▄▄▄\n"  
                "❌ *Zannen...* Subscription torn from the registry 📜\n"  
                "▹ Their coins return as cherry blossoms 🌸💸\n"  
                "▰▰▰▰▰▰▰▰▰▰▰▰▰\n" 
            ),  
            parse_mode='Markdown'  
        )  
    else:  
        await query.edit_message_text(  
            text=(  
                "▰▰▰▰▰▰▰▰▰▰▰▰▰\n"  
                "⚠️ *Yabai!* Forbidden scroll fragment detected 🧿\n"  
                "`🚫 Not recognized in ancient texts`\n"  
                "▰▰▰▰▰▰▰▰▰▰▰▰▰\n" 
            ),  
            parse_mode='Markdown'  
        )  
        release_lock(user_id)  

async def approve_subscription(key: str):
    subs = load_subscriptions()
    if key in subs:
        subs[key]['subscribed'] = True
        subs[key]['expiry_date'] = (datetime.now() + timedelta(days=SUBSCRIPTION_DAYS)).isoformat()
        save_subscriptions(subs)
        logger.info("Subscription approved for key: %s", key)
        
        user_id = subs[key].get("user-id")
        await bot.send_message(  
            chat_id=user_id,  
            text="🎉━━ *𝑨𝑷𝑷𝑹𝑶𝑽𝑬𝑫!* ━━🎉\n"  
            "▰▰▰▰▰▰▰▰▰▰▰▰▰\n"  
            "🌸 𝑵𝑬𝑿𝑻 𝑺𝑻𝑬𝑷𝑺 »\n"  
            "  🗝️ 1. 𝑨𝒅𝒅 𝒎𝒆 𝒂𝒔 𝑨𝑫𝑴𝑰𝑵\n"  
            "  🏮 2. 𝑼𝒔𝒆 /𝒔𝒕𝒂𝒓𝒕_𝒏𝒆𝒘𝒔\n\n"  
            "✨ 𝑴𝒊𝒛𝒖𝒌𝒊 𝒂𝒘𝒂𝒊𝒕𝒔 𝒚𝒐𝒖𝒓 𝒄𝒐𝒎𝒎𝒂𝒏𝒅~\n"
            "▰▰▰▰▰▰▰▰▰▰▰▰▰\n",  
            parse_mode='Markdown'  
        )  
        release_lock(user_id)
    else:
        logger.error("approve_subscription: key %s not found in subscriptions", key)

async def reject_subscription(user_id: str):
    subs = load_subscriptions()
    if str(user_id) in subs:
        del subs[str(user_id)]
        save_subscriptions(subs)
        release_lock(user_id)
