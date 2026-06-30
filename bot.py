import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable

from config import config
from database.connection import db_conn
from handlers import router
from middlewares.throttle import ThrottleMiddleware
from services.scheduler import start_scheduler

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://dtm-sertifikat-bot.onrender.com{WEBHOOK_PATH}"

logger = logging.getLogger(__name__)

class UpdateLoggerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        try:
            update_id = getattr(event, "update_id", "Unknown")
            user_id = "Unknown"
            
            if hasattr(event, "message") and event.message and event.message.from_user:
                user_id = event.message.from_user.id
            elif hasattr(event, "callback_query") and event.callback_query and event.callback_query.from_user:
                user_id = event.callback_query.from_user.id
                
            logger.info(f"Received update: {update_id} from user {user_id}")
        except Exception as e:
            logger.error(f"Error in UpdateLoggerMiddleware: {e}")
            
        return await handler(event, data)

async def on_startup(bot: Bot):
    await db_conn.connect()
    start_scheduler()
    if not config.debug:
        await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(bot: Bot):
    if not config.debug:
        await bot.delete_webhook(drop_pending_updates=True)
    await db_conn.disconnect()
    await bot.session.close()

async def main():
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )
    logger = logging.getLogger(__name__)

    logger.info("Starting bot...")

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    dp.update.outer_middleware(UpdateLoggerMiddleware())
    dp.message.middleware(ThrottleMiddleware())
    dp.include_router(router)

    if config.debug:
        logger.info("Starting in polling mode...")
        await db_conn.connect()
        start_scheduler()
        await bot.delete_webhook(drop_pending_updates=True)
        try:
            await dp.start_polling(bot)
        finally:
            await db_conn.disconnect()
            await bot.session.close()
    else:
        logger.info("Starting in webhook mode...")
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        app = web.Application()
        
        async def ping_handler(request: web.Request):
            return web.Response(text="Bot is running", status=200)
            
        app.router.add_get('/', ping_handler)
        app.router.add_get(WEBHOOK_PATH, ping_handler)
        
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        )
        webhook_requests_handler.register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)
        
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.environ.get("PORT", 10000))
        site = web.TCPSite(runner, host="0.0.0.0", port=port)
        await site.start()
        logger.info(f"Running app on 0.0.0.0:{port}")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
