import time
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message

class ThrottleMiddleware(BaseMiddleware):
    def __init__(self):
        self.user_requests = {}
        self.user_flood = {}
        self.cooldowns = {}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        now = time.time()
        
        # Clean up old cooldowns (simple check)
        if user_id in self.cooldowns:
            if now - self.cooldowns[user_id] < 30:
                return # In cooldown
            else:
                del self.cooldowns[user_id]
                
        # Flood protection: max 5 reqs per 10s
        if user_id not in self.user_flood:
            self.user_flood[user_id] = []
        
        self.user_flood[user_id] = [t for t in self.user_flood[user_id] if now - t < 10]
        self.user_flood[user_id].append(now)
        
        if len(self.user_flood[user_id]) >= 5:
            self.cooldowns[user_id] = now
            await event.answer("Siz juda tez xabar yuboryapsiz. 30 soniya kuting.")
            return

        # Global rate limit: max 30 reqs per 60s
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []
            
        self.user_requests[user_id] = [t for t in self.user_requests[user_id] if now - t < 60]
        self.user_requests[user_id].append(now)
        
        if len(self.user_requests[user_id]) > 30:
            return # Drop silently

        return await handler(event, data)
