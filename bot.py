import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_handler import SimpleRequestHandler, setup_application

from config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, PORT
from database.db import init_db
from middlewares.fsub import ForcedSubscriptionMiddleware
from handlers import user, admin, test_management, test_taking
from utils.scheduler import scheduler, reschedule_active_and_scheduled_tests

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def on_startup(bot: Bot):
    # Initialize DB indexes
    await init_db()
    
    # Start Scheduler
    scheduler.start()
    
    # Reschedule active and scheduled tests
    await reschedule_active_and_scheduled_tests(bot)
    
    # Set webhook
    await bot.set_webhook(
        url=WEBHOOK_URL,
        allowed_updates=["message", "callback_query", "chat_member"]
    )
    logger.info(f"Webhook set to: {WEBHOOK_URL}")

async def on_shutdown(bot: Bot):
    # Stop scheduler
    scheduler.shutdown()
    
    # Delete webhook
    await bot.delete_webhook()
    logger.info("Webhook deleted.")

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
    
    # Setup webhook application
    app = web.Application()
    
    # Configure request handler
    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot
    )
    webhook_handler.register(app, path=WEBHOOK_PATH)
    
    # Configure startup and shutdown events
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Setup application mapping
    setup_application(app, dp, bot=bot)
    
    # Start Web App
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
