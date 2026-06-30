from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from database.db import get_all_channels, is_admin
from keyboards.inline import get_subscription_keyboard
import logging

logger = logging.getLogger(__name__)

class ForcedSubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        # Retrieve user and bot from update data
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)
            
        # 1. Bypass check for bot admins and owner
        if await is_admin(user.id):
            return await handler(event, data)
            
        # 2. Get list of mandatory channels
        channels = await get_all_channels()
        if not channels:
            return await handler(event, data)
            
        bot = data.get("bot")
        unsubscribed_channels = []
        
        # 3. Check membership for each channel
        for ch in channels:
            try:
                member = await bot.get_chat_member(chat_id=ch["channel_id"], user_id=user.id)
                if member.status in ["left", "kicked"]:
                    unsubscribed_channels.append(ch)
            except Exception as e:
                logger.error(f"F-Sub middleware error checking channel {ch['channel_id']} for user {user.id}: {e}")
                # Treat as unsubscribed if check fails (e.g., bot kicked from channel or invalid channel ID)
                unsubscribed_channels.append(ch)
                
        if unsubscribed_channels:
            # Extract start payload to preserve deep-link context
            start_payload = "none"
            
            # If it's a check_sub callback query, we don't want to re-intercept with F-sub block
            # because the handler itself will check membership and alert user.
            if isinstance(event, CallbackQuery) and event.data and event.data.startswith("check_sub:"):
                # Pass to handler to show appropriate alert if they still haven't subscribed
                return await handler(event, data)
                
            if isinstance(event, Message) and event.text and event.text.startswith("/start"):
                parts = event.text.split()
                if len(parts) > 1:
                    start_payload = parts[1]
                    
            text = "⚠️ **Doimiy hamkor kanallarimizga a'zo bo'ling!**\n\nBotdan foydalanish uchun quyidagi kanallarga a'zo bo'lishingiz shart:"
            kb = get_subscription_keyboard(unsubscribed_channels, start_payload)
            
            if isinstance(event, Message):
                await event.answer(text, reply_markup=kb, parse_mode="Markdown")
            elif isinstance(event, CallbackQuery):
                await event.answer("⚠️ Botdan foydalanish uchun kanallarga a'zo bo'ling!", show_alert=True)
                # Avoid posting duplicate messages if current message already contains check_sub
                if not event.message.reply_markup or not any("check_sub" in str(row) for row in event.message.reply_markup.inline_keyboard):
                    await event.message.answer(text, reply_markup=kb, parse_mode="Markdown")
            return
            
        return await handler(event, data)
