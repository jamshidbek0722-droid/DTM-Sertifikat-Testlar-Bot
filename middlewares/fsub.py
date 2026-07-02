from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from database.db import get_all_channels, is_admin
from keyboards.inline import get_subscription_keyboard
import logging

logger = logging.getLogger(__name__)

class ForcedSubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)
            
        # Bypass check for bot admins and owner
        if await is_admin(user.id):
            return await handler(event, data)
            
        # Get list of active mandatory channels
        channels = await get_all_channels()
        if not channels:
            return await handler(event, data)
            
        bot = data.get("bot")
        unsubscribed_channels = []
        
        # Check membership for each channel
        for ch in channels:
            try:
                member = await bot.get_chat_member(chat_id=ch["channel_id"], user_id=user.id)
                if member.status in ["left", "kicked"]:
                    unsubscribed_channels.append(ch)
            except Exception as e:
                logger.error(f"F-Sub middleware error checking channel {ch['channel_id']} for user {user.id}: {e}")
                unsubscribed_channels.append(ch)
                
        if unsubscribed_channels:
            start_payload = "none"
            
            if isinstance(event, CallbackQuery) and event.data and event.data.startswith("check_sub:"):
                # Pass to handler to show appropriate alert if they still haven't subscribed
                return await handler(event, data)
                
            if isinstance(event, Message) and event.text and event.text.startswith("/start"):
                parts = event.text.split()
                if len(parts) > 1:
                    start_payload = parts[1]
                    
            text = "⚠️ <b>Doimiy hamkor kanallarimizga a'zo bo'ling!</b>\n\nBotdan foydalanish uchun quyidagi kanallarga a'zo bo'lishingiz shart:"
            kb = get_subscription_keyboard(unsubscribed_channels, start_payload)
            
            if isinstance(event, Message):
                await event.answer(text, reply_markup=kb, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.answer("⚠️ Botdan foydalanish uchun kanallarga a'zo bo'ling!", show_alert=True)
                if not event.message.reply_markup or not any("check_sub" in str(row) for row in event.message.reply_markup.inline_keyboard):
                    await event.message.answer(text, reply_markup=kb, parse_mode="HTML")
            return
            
        return await handler(event, data)
