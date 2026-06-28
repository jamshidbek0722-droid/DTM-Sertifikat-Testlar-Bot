from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from config import config

class AdminMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        
        user_id = event.from_user.id
        
        # Only allow OWNER_ID as requested
        if user_id != config.owner_id:
            # Drop silently
            return
            
        return await handler(event, data)
