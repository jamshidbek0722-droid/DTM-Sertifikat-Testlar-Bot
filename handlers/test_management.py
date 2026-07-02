import datetime
import random
import string
import asyncio
import html
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import (
    is_admin, is_owner, get_channels_by_admin, create_test, get_test, delete_test, get_tests_by_creator,
    get_all_genres, get_genre
)
from states.states import TestCreationStates
from keyboards.reply import get_admin_keyboard, get_cancel_keyboard
from config import DB_CHANNEL_ID
from utils.scheduler import schedule_test_jobs
import logging

logger = logging.getLogger(__name__)
router = Router()

def generate_test_id() -> str:
    # 6-digit unique test ID
    return "".join(random.choices(string.digits, k=6))

from keyboards.inline import get_admin_test_management_keyboard

# --- Test Management Menu ---

@router.message(F.text == "📝 Testlarni boshqarish")
async def show_test_management(message: Message):
    if not await is_admin(message.from_user.id):
        return
        
    user_id = message.from_user.id
    tests = await get_tests_by_creator(user_id)
    
    text = "📝 <b>Siz yaratgan testlar ro'yxati:</b>\n\n"
    if not tests:
        text += "Siz hali test yaratmagansiz."
    else:
        for idx, t in enumerate(tests, 1):
            status_emoji = "⏳" if t['status'] == "scheduled" else "🟢" if t['status'] == "active" else "🔴"
            start_local = t['start_time'] + datetime.timedelta(hours=5) # Show in UTC+5
            
            # Fetch genre name
            genre_name = "Nomalum"
            if t.get("genre_id"):
                g = await get_genre(t["genre_id"])
                if g:
                    genre_name = g["name"]
                    
            text += (
                f"{idx}. <b>{html.escape(t.get('test_name', 'Nomsiz'))}</b> ({html.escape(genre_name)})\n"
                f"   📋 Test ID: <code>{t['test_id']}</code> ({status_emoji} {t['status'].upper()})\n"
                f"   📅 Boshlanishi: {start_local.strftime('%Y-%m-%d %H:%M')} (UZB time)\n"
                f"   ⏱ Davomiyligi: {t['duration_minutes']} daqiqa\n"
                f"   📢 Kanal ID: <code>{t['channel_id']}</code>\n\n"
            )
            
    kb = get_admin_test_management_keyboard()
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

# --- Create Test FSM ---

@router.callback_query(F.data == "admin_create_test")
async def start_create_test(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if not await is_admin(call.from_user.id):
        return
        
    await state.set_state(TestCreationStates.waiting_for_test_name)
    cancel_kb = get_cancel_keyboard()
    await call.message.answer(
        "📝 <b>Yangi test yaratish boshlandi.</b>\n\n"
        "Iltimos, test nomini kiriting:",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )

@router.message(TestCreationStates.waiting_for_test_name)
async def process_test_name(message: Message, state: FSMContext):
    test_name = message.text.strip()
    if not test_name:
        await message.answer("Test nomini kiriting:")
        return
    await state.update_data(test_name=test_name)
    
    # Check if there are genres in DB
    genres = await get_all_genres()
    if not genres:
        await state.clear()
        kb = await get_admin_keyboard(message.from_user.id)
        await message.answer("⚠️ Hozirda hech qanday janr yaratilmagan. Avval '📚 Janrlarni boshqarish' bo'limida janr yarating.", reply_markup=kb)
        return
        
    from keyboards.inline import get_genre_selection_keyboard
    kb = get_genre_selection_keyboard(genres)
    await state.set_state(TestCreationStates.waiting_for_genre)
    await message.answer("📚 Test janrini tanlang:", reply_markup=kb)

@router.callback_query(TestCreationStates.waiting_for_genre, F.data.startswith("create_test_genre:"))
async def process_test_genre(call: CallbackQuery, state: FSMContext):
    await call.answer()
    genre_id = call.data.split(":")[1]
    await state.update_data(genre_id=genre_id)
    
    await state.set_state(TestCreationStates.waiting_for_file)
    cancel_kb = get_cancel_keyboard()
    await call.message.answer(
        "📝 <b>Test savollarini yuboring.</b>\n\n"
        "Iltimos, test savollari faylini yuboring (PDF, Rasm yoki istalgan hujjat):",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )

# Media group cache barrier to handle multiple images
media_group_cache = {}

@router.message(TestCreationStates.waiting_for_file)
async def process_test_file(message: Message, state: FSMContext):
    if message.media_group_id:
        mg_id = message.media_group_id
        if mg_id not in media_group_cache:
            media_group_cache[mg_id] = []
            is_first = True
        else:
            is_first = False
            
        if message.document:
            media_group_cache[mg_id].append({"file_id": message.document.file_id, "file_type": "document"})
        elif message.photo:
            media_group_cache[mg_id].append({"file_id": message.photo[-1].file_id, "file_type": "photo"})
        elif message.video:
            media_group_cache[mg_id].append({"file_id": message.video.file_id, "file_type": "video"})
            
        if not is_first:
            return
            
        await asyncio.sleep(0.5)
        new_files = media_group_cache.pop(mg_id, [])
        if not new_files:
            return
            
        data = await state.get_data()
        files = data.get("files", [])
        files.extend(new_files)
        await state.update_data(files=files)
    else:
        # Single file
        file_id = None
        file_type = None
        if message.document:
            file_id = message.document.file_id
            file_type = "document"
        elif message.photo:
            file_id = message.photo[-1].file_id
            file_type = "photo"
        elif message.video:
            file_id = message.video.file_id
            file_type = "video"
        else:
            await message.answer("⚠️ Iltimos, faqat PDF fayl, Hujjat yoki Rasm yuboring:")
            return
            
        data = await state.get_data()
        files = data.get("files", [])
        files.append({"file_id": file_id, "file_type": file_type})
        await state.update_data(files=files)
        
    data = await state.get_data()
    files = data.get("files", [])
    count = len(files)
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Rasmlarni saqlash va davom etish", callback_data="admin_save_files")]
        ]
    )
    await message.answer(
        f"📎 Fayl muvaffaqiyatli qabul qilindi. (Jami: {count} ta fayl)\n\n"
        f"Yana rasm yoki hujjat yuborishingiz mumkin. Barcha fayllarni yuborib bo'lgach, "
        f"quyidagi '📥 Rasmlarni saqlash va davom etish' tugmasini bosing:",
        reply_markup=kb
    )

@router.callback_query(TestCreationStates.waiting_for_file, F.data == "admin_save_files")
async def save_uploaded_files(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()
    data = await state.get_data()
    files = data.get("files", [])
    if not files:
        await call.message.answer("⚠️ Iltimos, avval test savollari rasm yoki hujjat faylini yuboring!")
        return
        
    status_msg = await call.message.answer("🔄 Fayllar log kanaliga yuklanmoqda, iltimos kuting...")
    
    forwarded_files = []
    # Send files to DB_CHANNEL_ID safely and get the new file IDs
    for item in files:
        f_id = item["file_id"]
        f_type = item["file_type"]
        try:
            if f_type == "photo":
                sent_msg = await bot.send_photo(chat_id=DB_CHANNEL_ID, photo=f_id)
                new_id = sent_msg.photo[-1].file_id
                forwarded_files.append({"file_id": new_id, "file_type": "photo"})
            elif f_type == "video":
                sent_msg = await bot.send_video(chat_id=DB_CHANNEL_ID, video=f_id)
                new_id = sent_msg.video.file_id
                forwarded_files.append({"file_id": new_id, "file_type": "video"})
            else:
                sent_msg = await bot.send_document(chat_id=DB_CHANNEL_ID, document=f_id)
                new_id = sent_msg.document.file_id
                forwarded_files.append({"file_id": new_id, "file_type": "document"})
        except Exception as e:
            logger.exception("Faylni log kanaliga yuborishda xatolik yuz berdi:")
            # Fallback to direct file_id if channel copy fails
            forwarded_files.append({"file_id": f_id, "file_type": f_type})
            
    await state.update_data(files=forwarded_files)
    
    try:
        await status_msg.delete()
    except Exception:
        pass
        
    await state.set_state(TestCreationStates.waiting_for_keys)
    await call.message.answer("Javoblar kalitini yuboring (masalan, `abcdabcd...` yoki `1a2b3c...`):")

@router.message(TestCreationStates.waiting_for_keys)
async def process_test_keys(message: Message, state: FSMContext):
    raw_keys = message.text.strip().lower()
    if not raw_keys:
        await message.answer("Iltimos, matnli javoblar kalitini yuboring:")
        return
        
    # Standard clean up
    import re
    cleaned = raw_keys.replace(" ", "").replace("\n", "")
    
    # Custom starting number detection: check if keys starts with custom numbers e.g. "31a32b"
    if any(char.isdigit() for char in cleaned):
        pairs = re.findall(r"(\d+)([a-d])", cleaned)
        if not pairs:
            await message.answer("⚠️ Kalit formati noto'g'ri. Masalan: `31a32b33c` formatida kiriting:")
            return
        # Verify sequential order (we don't strictly require sorting, but save as dictionary or map)
        # Store answer key as string mapped dynamically, but wait, evaluator will match.
        # To support non-1 starting number, we store answer key exactly as we parsed.
        # Let's save a structured object or string. Saving it as "31a32b33c" as is, so the evaluator
        # can easily parse it!
        # Wait, what if we also extract starting index?
        # Let's clean the continuous digits + letter format. Let's make sure it's valid:
        answer_key = "".join(f"{num}{char}" for num, char in pairs)
    else:
        # Standard continuous string starting from 1
        if not all(char in "abcd" for char in cleaned):
            await message.answer("⚠️ Kalit faqat a, b, c, d harflaridan iborat bo'lishi kerak. Qaytadan kiriting:")
            return
        answer_key = cleaned
        
    await state.update_data(answer_key=answer_key)
    await state.set_state(TestCreationStates.waiting_for_solutions)
    await message.answer(
        "Test yechimi (video link yoki tushuntirish matni/media) yuboring.\n"
        "Agar yechim bo'lmasa, `none` yuboring:"
    )

@router.message(TestCreationStates.waiting_for_solutions, F.content_type.in_({'text', 'photo', 'video', 'document'}))
async def process_test_solutions(message: Message, state: FSMContext):
    solutions_text = ""
    solutions_media = None
    
    if message.text:
        text = message.text.strip()
        if text.lower() != "none":
            solutions_text = text
    elif message.photo:
        solutions_media = {"file_id": message.photo[-1].file_id, "file_type": "photo"}
        solutions_text = message.caption or ""
    elif message.video:
        solutions_media = {"file_id": message.video.file_id, "file_type": "video"}
        solutions_text = message.caption or ""
    elif message.document:
        solutions_media = {"file_id": message.document.file_id, "file_type": "document"}
        solutions_text = message.caption or ""
        
    await state.update_data(solutions_text=solutions_text, solutions_media=solutions_media)
    
    # Next, ask which channel to assign
    admin_id = message.from_user.id
    from database.db import get_test_channels_by_admin
    channels = await get_test_channels_by_admin(admin_id)
    
    if not channels:
        await state.clear()
        kb = await get_admin_keyboard(admin_id)
        await message.answer(
            "⚠️ Sizda ulangan test kanallari yo'q. Avval '🔗 Mening kanallarim' bo'limida kanal qo'shing, keyin test yarating.",
            reply_markup=kb
        )
        return
        
    buttons = []
    for ch in channels:
        buttons.append([InlineKeyboardButton(text=ch['title'], callback_data=f"assign_chan:{ch['channel_id']}")])
        
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await state.set_state(TestCreationStates.waiting_for_channel)
    await message.answer("Ushbu test qaysi kanalda o'tkaziladi? Kanalni tanlang:", reply_markup=kb)

@router.callback_query(TestCreationStates.waiting_for_channel, F.data.startswith("assign_chan:"))
async def process_test_channel(call: CallbackQuery, state: FSMContext):
    await call.answer()
    channel_id = int(call.data.split(":")[1])
    
    await state.update_data(channel_id=channel_id)
    await state.set_state(TestCreationStates.waiting_for_start_time)
    
    uzb_now = datetime.datetime.utcnow() + datetime.timedelta(hours=5)
    await call.message.answer(
        f"Test boshlanish vaqtini kiriting.\n"
        f"Format: `YYYY-MM-DD HH:MM` (masalan, `2026-06-30 20:30`)\n\n"
        f"🕒 Hozirgi UZB vaqti: `{(uzb_now).strftime('%Y-%m-%d %H:%M')}`",
        parse_mode="Markdown"
    )

@router.message(TestCreationStates.waiting_for_start_time)
async def process_test_start_time(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        local_dt = datetime.datetime.strptime(text, "%Y-%m-%d %H:%M")
        utc_dt = local_dt - datetime.timedelta(hours=5)
        if utc_dt < datetime.datetime.utcnow() - datetime.timedelta(minutes=5):
            await message.answer("⚠️ Boshlanish vaqti o'tib ketgan vaqt bo'la olmaydi. Kelajakdagi vaqtni kiriting:")
            return
    except ValueError:
        await message.answer("⚠️ Noto'g'ri format. Iltimos, `YYYY-MM-DD HH:MM` formatida kiriting:")
        return
        
    await state.update_data(start_time=utc_dt.isoformat())
    await state.set_state(TestCreationStates.waiting_for_duration)
    await message.answer("Test davomiyligini kiriting (daqiqalarda, masalan, `90`):")

@router.message(TestCreationStates.waiting_for_duration)
async def process_test_duration(message: Message, state: FSMContext, bot: Bot):
    text = message.text.strip()
    try:
        duration = int(text)
        if duration <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Davomiylik musbat butun son bo'lishi kerak. Qaytadan kiriting:")
        return
        
    data = await state.get_data()
    test_id = generate_test_id()
    admin_id = message.from_user.id
    
    file_ids = data.get('files', [])
    answer_key = data['answer_key']
    solutions_text = data['solutions_text']
    solutions_media = data.get('solutions_media')
    channel_id = data['channel_id']
    start_time = datetime.datetime.fromisoformat(data['start_time'])
    test_name = data['test_name']
    genre_id = data['genre_id']
    
    success = await create_test(
        test_id=test_id,
        creator_id=admin_id,
        file_ids=file_ids,
        answer_key=answer_key,
        solutions_text=solutions_text,
        channel_id=channel_id,
        start_time=start_time,
        duration_minutes=duration,
        test_name=test_name,
        genre_id=genre_id,
        solutions_media=solutions_media
    )
    
    await state.clear()
    kb = await get_admin_keyboard(admin_id)
    
    if success:
        await schedule_test_jobs(bot, test_id, start_time, duration)
        local_start = start_time + datetime.timedelta(hours=5)
        await message.answer(
            f"🎉 <b>Test muvaffaqiyatli rejalashtirildi!</b>\n\n"
            f"📋 Test nomi: <b>{html.escape(test_name)}</b>\n"
            f"📋 Test ID: <code>{test_id}</code>\n"
            f"📅 Boshlanishi: {local_start.strftime('%Y-%m-%d %H:%M')} (UZB)\n"
            f"⏱ Davomiyligi: {duration} daqiqa\n"
            f"🔑 Kalit: <code>{answer_key.upper()}</code>\n\n"
            f"Bot belgilangan vaqtda testni kanalga avtomatik joylashtiradi.",
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        await message.answer("⚠️ Test yaratishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.", reply_markup=kb)

# --- Delete Test ---

@router.callback_query(F.data == "admin_delete_test")
async def start_delete_test(call: CallbackQuery):
    await call.answer()
    user_id = call.from_user.id
    if not await is_admin(user_id):
        return
        
    tests = await get_tests_by_creator(user_id)
    if not tests:
        await call.message.answer("O'chirish uchun siz yaratgan testlar mavjud emas.")
        return
        
    buttons = []
    for t in tests:
        buttons.append([InlineKeyboardButton(text=f"🗑 ID: {t['test_id']} ({t['status']})", callback_data=f"del_test:{t['test_id']}")])
        
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await call.message.answer("O'chirmoqchi bo'lgan testni tanlang:", reply_markup=kb)

@router.callback_query(F.data.startswith("del_test:"))
async def process_delete_test(call: CallbackQuery):
    await call.answer()
    user_id = call.from_user.id
    if not await is_admin(user_id):
        return
        
    test_id = call.data.split(":")[1]
    test = await get_test(test_id)
    if not test:
        await call.message.answer("Test topilmadi.")
        return
        
    if test.get("creator_id") != user_id and not await is_owner(user_id):
        await call.message.answer("⚠️ Siz ushbu testni o'chira olmaysiz.")
        return
        
    success = await delete_test(test_id)
    if success:
        try:
            from utils.scheduler import scheduler
            scheduler.remove_job(f"start_{test_id}")
            scheduler.remove_job(f"end_{test_id}")
        except Exception:
            pass
            
        await call.message.delete()
        await call.message.answer("✅ Test muvaffaqiyatli o'chirildi.")
    else:
        await call.message.answer("⚠️ Testni o'chirishda xatolik yuz berdi.")
