from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from config import config
from database.connection import db_conn

class AdminMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        
        user_id = event.from_user.id
        
        is_admin = False
        if user_id == config.owner_id:
            is_admin = True
        else:
            # Check DB if user is an admin
            admin = await db_conn.db.admins.find_one({"user_id": user_id})
            if admin:
                is_admin = True
                
        if not is_admin:
            if isinstance(event, Message):
                await event.answer("Sizda admin huquqi yo'q.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Sizda admin huquqi yo'q.", show_alert=True)
            return
            
        return await handler(event, data)
