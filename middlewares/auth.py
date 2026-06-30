from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from config import config
import logging
import os

logger = logging.getLogger(__name__)

class AdminMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        try:
            user_id = event.from_user.id
            # Safely fetch, strip and cast OWNER_ID to int just in case
            owner_id_val = os.getenv("OWNER_ID", str(config.owner_id)).strip()
            owner_id = int(owner_id_val)
            
            if int(user_id) != owner_id:
                logger.warning(f"Unauthorized access attempt by {user_id}. Expected OWNER_ID: {owner_id}")
                return # Drop silently
        except Exception as e:
            logger.error(f"Error in AdminMiddleware: {e}")
            return
            
        return await handler(event, data)
