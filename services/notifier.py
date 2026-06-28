import datetime
from datetime import timezone
from config import config
from database.repositories.test_repo import TestRepo
from database.models import TestStatus
from services.leaderboard import generate_leaderboard_text

async def post_test_to_channel(test_id: str, channel_id: int):
    from aiogram import Bot
    from aiogram.enums import ParseMode
    from aiogram.client.default import DefaultBotProperties
    from keyboards.user_kb import get_join_test_kb
    from database.connection import db_conn
    
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    test = await TestRepo.get_test_by_id(test_id)
    if not test:
        await bot.session.close()
        return
        
    test.status = TestStatus.active
    test.start_time = datetime.datetime.now(timezone.utc)
    test.end_time = test.start_time + datetime.timedelta(minutes=test.duration)
    
    await db_conn.db.tests.update_one(
        {"test_id": test_id},
        {"$set": {
            "status": test.status.value,
            "start_time": test.start_time,
            "end_time": test.end_time
        }}
    )
    
    caption = f"📚 Yangi Test: {test.title}\n📖 Fan: {test.subject}\n⏱ Davomiyligi: {test.duration} daqiqa\n\nQatnashish uchun tugmani bosing!"
    await bot.send_document(
        chat_id=channel_id,
        document=test.pdf_file_id,
        caption=caption,
        reply_markup=get_join_test_kb(test_id)
    )
    await bot.session.close()

async def post_leaderboard_to_channel(test_id: str, channel_id: int):
    from aiogram import Bot
    from aiogram.enums import ParseMode
    from aiogram.client.default import DefaultBotProperties
    
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    await TestRepo.update_test_status(test_id, TestStatus.completed)
    
    text = await generate_leaderboard_text(test_id)
    if text:
        await bot.send_message(chat_id=channel_id, text=text)
        
    await bot.session.close()

async def post_solution_to_channel(test_id: str, channel_id: int):
    from aiogram import Bot
    from aiogram.enums import ParseMode
    from aiogram.client.default import DefaultBotProperties
    
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    test = await TestRepo.get_test_by_id(test_id)
    if test and test.solution_file_id:
        await bot.send_document(
            chat_id=channel_id,
            document=test.solution_file_id,
            caption=f"📘 Yechimlar: {test.title}"
        )
    await bot.session.close()
