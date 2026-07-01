import logging
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, PORT
from database.db import init_db
from middlewares.fsub import ForcedSubscriptionMiddleware
from handlers import user, admin, test_management, test_taking
from utils.scheduler import scheduler, reschedule_active_and_scheduled_tests

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def handle_webhook(request: web.Request) -> web.Response:
    """
    Asynchronously processes updates in a background task to instantly acknowledge the webhook.
    Guarantees Telegram receives HTTP 200 OK immediately, eliminating retry storms and timeouts.
    """
    bot = request.app["bot"]
    dp = request.app["dp"]
    try:
        update_json = await request.json()
        update = Update.model_validate(update_json, context={"bot": bot})
        # Process update asynchronously in background
        asyncio.create_task(dp.feed_update(bot, update))
    except Exception as e:
        logger.exception("Error processing webhook update:")
        
    return web.Response(text="ok", status=200)

async def on_startup(bot: Bot):
    logger.info("Initializing database...")
    await init_db()
    
    logger.info("Starting scheduler...")
    scheduler.start()
    
    logger.info("Recovering active and scheduled tests...")
    await reschedule_active_and_scheduled_tests(bot)
    
    logger.info(f"Setting webhook to: {WEBHOOK_URL}...")
    await bot.set_webhook(
        url=WEBHOOK_URL,
        allowed_updates=["message", "callback_query", "chat_member"]
    )
    logger.info("Webhook successfully registered.")

async def on_shutdown(bot: Bot):
    logger.info("Shutting down scheduler...")
    scheduler.shutdown()
    
    logger.info("Removing webhook...")
    await bot.delete_webhook()
    
    logger.info("Closing bot session...")
    await bot.session.close()
    logger.info("Shutdown completed.")

def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register Middlewares
    dp.message.outer_middleware(ForcedSubscriptionMiddleware())
    dp.callback_query.outer_middleware(ForcedSubscriptionMiddleware())
    
    # Register Routers
    dp.include_router(user.router)
    dp.include_router(test_taking.router)
    dp.include_router(admin.router)
    dp.include_router(test_management.router)
    
    # Setup Webapp
    app = web.Application()
    app["bot"] = bot
    app["dp"] = dp
    
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    
    # Register app startup and shutdown hooks
    app.on_startup.append(lambda a: on_startup(bot))
    app.on_shutdown.append(lambda a: on_shutdown(bot))
    
    # Start web app
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
