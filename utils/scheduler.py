import datetime
import html
from datetime import timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.asyncio import AsyncIOExecutor
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.media_group import MediaGroupBuilder
from database.db import (
    get_test, update_test_status, update_test_post_msg_id, get_submissions_for_test,
    get_user, get_global_footer, tests_col
)
import logging

logger = logging.getLogger(__name__)

# Initialize APScheduler explicitly in UTC to ensure it works uniformly on any host
scheduler = AsyncIOScheduler(
    executors={'default': AsyncIOExecutor()},
    timezone=timezone.utc
)

async def start_test_job(bot: Bot, test_id: str):
    logger.info(f"Starting test job for test_id: {test_id}")
    test = await get_test(test_id)
    if not test:
        logger.error(f"Test {test_id} not found in database.")
        return
        
    if test.get("status") == "active" and test.get("test_post_msg_id") is not None:
        logger.warning(f"Test {test_id} is already active and posted. Skipping start.")
        return
        
    if test.get("status") not in ["scheduled", "active"]:
        logger.warning(f"Test {test_id} status is {test.get('status')}. Skipping start.")
        return
        
    # Update status to active
    await update_test_status(test_id, "active")
    
    # Get bot username for deep link
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    
    # Prepare caption & keyboard
    footer = await get_global_footer()
    footer_text = f"\n\n{footer}" if footer else ""
    
    test_name = test.get("test_name", "Nomsiz test")
    
    caption = (
        f"<b>{html.escape(test_name)}</b>\n\n"
        f"📝 <b>YANGI TEST BOSHLANDI!</b>\n\n"
        f"📋 Test ID: <code>{test_id}</code>\n"
        f"✍️ Savollar soni: <b>{len(test['answer_key'])}</b> ta\n"
        f"⏱ Vaqt: <b>{test['duration_minutes']}</b> daqiqa\n\n"
        f"Javoblaringizni yuborish uchun quyidagi tugmani bosing va botga o'ting:👇{footer_text}"
    )
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Javob Yuborish", url=f"https://t.me/{bot_username}?start=test_{test_id}")]
        ]
    )
    
    file_ids = test.get("file_ids", [])
    if not file_ids and test.get("file_id"):
        file_ids = [{"file_id": test.get("file_id"), "file_type": test.get("file_type", "document")}]
        
    channel_id = test["channel_id"]
    sent_msg = None
    
    try:
        # Check if we have multiple photos to group as Album
        if len(file_ids) > 1 and all(f.get("file_type") == "photo" for f in file_ids):
            media_group = MediaGroupBuilder()
            for idx, f in enumerate(file_ids):
                if idx == 0:
                    media_group.add_photo(media=f["file_id"], caption=caption, parse_mode="HTML")
                else:
                    media_group.add_photo(media=f["file_id"])
            sent_msgs = await bot.send_media_group(chat_id=channel_id, media=media_group.build())
            if sent_msgs:
                sent_msg = sent_msgs[0]
                await update_test_post_msg_id(test_id, sent_msg.message_id)
                logger.info(f"Test {test_id} successfully posted as Album to channel {channel_id}.")
                
                # Send a companion message with the inline keyboard
                try:
                    await bot.send_message(
                        chat_id=channel_id,
                        text=f"✍️ <b>{html.escape(test_name)}</b> testiga javob yuborish uchun quyidagi tugmani bosing:",
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        elif file_ids:
            # Post single file or sequential fallback
            first_file = file_ids[0]
            f_id = first_file.get("file_id")
            f_type = first_file.get("file_type", "document")
            
            if f_type == "photo":
                sent_msg = await bot.send_photo(
                    chat_id=channel_id,
                    photo=f_id,
                    caption=caption,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            elif f_type == "video":
                sent_msg = await bot.send_video(
                    chat_id=channel_id,
                    video=f_id,
                    caption=caption,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            else:
                sent_msg = await bot.send_document(
                    chat_id=channel_id,
                    document=f_id,
                    caption=caption,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                
            if sent_msg:
                await update_test_post_msg_id(test_id, sent_msg.message_id)
                logger.info(f"Test {test_id} successfully posted to channel {channel_id}.")
                
            # Post any additional non-photo files sequentially
            for idx, item in enumerate(file_ids[1:], start=2):
                f_id = item.get("file_id")
                f_type = item.get("file_type", "document")
                try:
                    if f_type == "photo":
                        await bot.send_photo(
                            chat_id=channel_id,
                            photo=f_id,
                            caption=f"📊 Test ID: <code>{test_id}</code> (davomi - {idx}-fayl)",
                            parse_mode="HTML"
                        )
                    elif f_type == "video":
                        await bot.send_video(
                            chat_id=channel_id,
                            video=f_id,
                            caption=f"📊 Test ID: <code>{test_id}</code> (davomi - {idx}-fayl)",
                            parse_mode="HTML"
                        )
                    else:
                        await bot.send_document(
                            chat_id=channel_id,
                            document=f_id,
                            caption=f"📊 Test ID: <code>{test_id}</code> (davomi - {idx}-fayl)",
                            parse_mode="HTML"
                        )
                except Exception as e:
                    logger.error(f"Failed to post additional file {f_id} to channel {channel_id}: {e}")
        else:
            # Post text only if no files
            sent_msg = await bot.send_message(
                chat_id=channel_id,
                text=caption,
                reply_markup=kb,
                parse_mode="HTML"
            )
            if sent_msg:
                await update_test_post_msg_id(test_id, sent_msg.message_id)
    except Exception as e:
        logger.error(f"Failed to post test {test_id} to channel {channel_id}: {e}")

async def end_test_job(bot: Bot, test_id: str):
    logger.info(f"Ending test job for test_id: {test_id}")
    test = await get_test(test_id)
    if not test:
        logger.error(f"Test {test_id} not found in database.")
        return
        
    if test.get("status") == "finished":
        logger.warning(f"Test {test_id} is already finished. Skipping.")
        return
        
    # Update status to finished
    await update_test_status(test_id, "finished")
    
    # Aggregate results and generate leaderboard
    submissions = await get_submissions_for_test(test_id)
    channel_id = test["channel_id"]
    post_msg_id = test.get("test_post_msg_id")
    test_name = test.get("test_name", "Nomsiz test")
    
    leaderboard = (
        f"🏁 <b>TEST YAKUNLANDI!</b>\n"
        f"📝 Test nomi: <b>{html.escape(test_name)}</b>\n"
        f"📋 Test ID: <code>{test_id}</code>\n\n"
        f"🏆 <b>Natijalar (Top 20):</b>\n"
    )
    
    if not submissions:
        leaderboard += "Ushbu testda hech kim ishtirok etmadi."
    else:
        for idx, sub in enumerate(submissions[:20], 1):
            user = await get_user(sub["user_id"])
            user_name = user.get("name", "Foydalanuvchi") if user else "Foydalanuvchi"
            t_seconds = sub.get("time_taken_seconds", 0)
            mins = t_seconds // 60
            secs = t_seconds % 60
            time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
            
            leaderboard += f"{idx}. <b>{html.escape(user_name)}</b> — {sub['correct_count']}/{sub['total_count']} ({sub['score']}%) [⏱ {time_str}]\n"
            
        leaderboard += f"\n📥 Jami ishtirokchilar soni: <b>{len(submissions)}</b> ta"
        
    footer = await get_global_footer()
    if footer:
        leaderboard += f"\n\n{footer}"
        
    # Send leaderboard to channel
    try:
        if post_msg_id:
            await bot.send_message(
                chat_id=channel_id,
                text=leaderboard,
                reply_to_message_id=post_msg_id,
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=channel_id,
                text=leaderboard,
                parse_mode="HTML"
            )
        logger.info(f"Leaderboard for test {test_id} posted to channel {channel_id}.")
    except Exception as e:
        logger.error(f"Failed to post leaderboard for test {test_id} to channel {channel_id}: {e}")
        
    # Post solutions if provided
    solutions = test.get("solutions_text")
    solutions_media = test.get("solutions_media")
    footer_text = f"\n\n{footer}" if footer else ""
    
    if solutions or solutions_media:
        caption_sol = f"💡 <b>Test ID <code>{test_id}</code> yechimlari:</b>\n\n{solutions or ''}{footer_text}"
        try:
            if solutions_media:
                f_id = solutions_media.get("file_id")
                f_type = solutions_media.get("file_type")
                if f_type == "photo":
                    await bot.send_photo(
                        chat_id=channel_id,
                        photo=f_id,
                        caption=caption_sol,
                        parse_mode="HTML",
                        reply_to_message_id=post_msg_id if post_msg_id else None
                    )
                elif f_type == "video":
                    await bot.send_video(
                        chat_id=channel_id,
                        video=f_id,
                        caption=caption_sol,
                        parse_mode="HTML",
                        reply_to_message_id=post_msg_id if post_msg_id else None
                    )
                else:
                    await bot.send_document(
                        chat_id=channel_id,
                        document=f_id,
                        caption=caption_sol,
                        parse_mode="HTML",
                        reply_to_message_id=post_msg_id if post_msg_id else None
                    )
            else:
                await bot.send_message(
                    chat_id=channel_id,
                    text=caption_sol,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_to_message_id=post_msg_id if post_msg_id else None
                )
            logger.info(f"Solutions for test {test_id} posted.")
        except Exception as e:
            logger.error(f"Failed to post solutions for test {test_id}: {e}")

async def schedule_test_jobs(bot: Bot, test_id: str, start_time: datetime.datetime, duration_minutes: int):
    """Schedules start and end jobs for a test"""
    # Ensure start_time is timezone-aware UTC
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
        
    end_time = start_time + datetime.timedelta(minutes=duration_minutes)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    
    # Schedule Start Job
    scheduler.add_job(
        start_test_job,
        "date",
        run_date=start_time,
        args=[bot, test_id],
        id=f"start_{test_id}",
        replace_existing=True
    )
    
    # Schedule End Job
    scheduler.add_job(
        end_test_job,
        "date",
        run_date=end_time,
        args=[bot, test_id],
        id=f"end_{test_id}",
        replace_existing=True
    )
    logger.info(f"Scheduled start/end jobs for test {test_id} (Start: {start_time}, End: {end_time})")

async def reschedule_active_and_scheduled_tests(bot: Bot):
    """Recovers and reschedules all tests on bot startup"""
    now = datetime.datetime.now(timezone.utc)
    
    # Find all scheduled or active tests
    cursor = tests_col.find({"status": {"$in": ["scheduled", "active"]}})
    tests = await cursor.to_list(length=None)
    
    for t in tests:
        test_id = t["test_id"]
        start_time = t["start_time"]
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
            
        duration = t["duration_minutes"]
        end_time = start_time + datetime.timedelta(minutes=duration)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
            
        status = t["status"]
        
        if status == "scheduled":
            if start_time > now:
                # Schedule both normally
                await schedule_test_jobs(bot, test_id, start_time, duration)
            elif start_time <= now < end_time:
                # Started in the past but hasn't ended. Start immediately and schedule end.
                logger.info(f"Recovery: Starting scheduled test {test_id} immediately.")
                await start_test_job(bot, test_id)
                scheduler.add_job(
                    end_test_job,
                    "date",
                    run_date=end_time,
                    args=[bot, test_id],
                    id=f"end_{test_id}",
                    replace_existing=True
                )
            else:
                # Both start and end times have passed. Finalize it immediately.
                logger.info(f"Recovery: Finishing missed test {test_id} immediately.")
                await start_test_job(bot, test_id)
                await end_test_job(bot, test_id)
                
        elif status == "active":
            if now < end_time:
                if t.get("test_post_msg_id") is None:
                    logger.info(f"Recovery: Test {test_id} status is active but test_post_msg_id is None (post failed). Starting job again.")
                    await start_test_job(bot, test_id)
                else:
                    logger.info(f"Recovery: Rescheduled end job for active test {test_id} at {end_time}")
                
                # Reschedule end job
                scheduler.add_job(
                    end_test_job,
                    "date",
                    run_date=end_time,
                    args=[bot, test_id],
                    id=f"end_{test_id}",
                    replace_existing=True
                )
            else:
                # Duration passed. Finish it immediately.
                logger.info(f"Recovery: Ending active test {test_id} immediately.")
                await end_test_job(bot, test_id)
