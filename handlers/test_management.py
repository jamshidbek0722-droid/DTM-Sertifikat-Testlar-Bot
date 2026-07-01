import datetime
import random
import string
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import (
    is_admin, is_owner, get_channels_by_admin, create_test, get_test, delete_test, get_tests_by_creator
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

# --- Test Management Menu ---

@router.message(F.text == "📝 Test Management")
async def show_test_management(message: Message):
    if not await is_admin(message.from_user.id):
        return
        
    user_id = message.from_user.id
    tests = await get_tests_by_creator(user_id)
    
    text = "📝 **Siz yaratgan testlar ro'yxati:**\n\n"
    if not tests:
        text += "Siz hali test yaratmagansiz."
    else:
        for idx, t in enumerate(tests, 1):
            status_emoji = "⏳" if t['status'] == "scheduled" else "🟢" if t['status'] == "active" else "🔴"
            start_local = t['start_time'] + datetime.timedelta(hours=5) # Show in UTC+5
            text += (
                f"{idx}. Test ID: `{t['test_id']}` ({status_emoji} {t['status'].upper()})\n"
                f"   📅 Boshlanishi: {start_local.strftime('%Y-%m-%d %H:%M')} (UZB time)\n"
                f"   ⏱ Davomiyligi: {t['duration_minutes']} daqiqa\n"
                f"   📢 Kanal ID: `{t['channel_id']}`\n\n"
            )
            
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Yangi Test Yaratish", callback_data="admin_create_test"),
                InlineKeyboardButton(text="🗑 Testni O'chirish", callback_data="admin_delete_test")
            ]
        ]
    )
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

# --- Create Test FSM ---

@router.callback_query(F.data == "admin_create_test")
async def start_create_test(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if not await is_admin(call.from_user.id):
        return
        
    await state.set_state(TestCreationStates.waiting_for_file)
    cancel_kb = get_cancel_keyboard()
    await call.message.answer(
        "📝 **Yangi test yaratish boshlandi.**\n\n"
        "Iltimos, test savollari faylini yuboring (PDF, Rasm yoki istalgan hujjat):",
        reply_markup=cancel_kb,
        parse_mode="Markdown"
    )

@router.message(TestCreationStates.waiting_for_file)
async def process_test_file(message: Message, state: FSMContext, bot: Bot):
    # Determine type of file
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

    # Try copying the message to the DB_CHANNEL_ID
    try:
        copied_msg = await bot.copy_message(
            chat_id=DB_CHANNEL_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        if copied_msg.document:
            file_id = copied_msg.document.file_id
            file_type = "document"
        elif copied_msg.photo:
            file_id = copied_msg.photo[-1].file_id
            file_type = "photo"
        elif copied_msg.video:
            file_id = copied_msg.video.file_id
            file_type = "video"
    except Exception as e:
        logger.warning(f"Could not forward file to database channel (falling back to direct file_id): {e}")

    # Retrieve current files list from state and append
    data = await state.get_data()
    files = data.get("files", [])
    files.append({"file_id": file_id, "file_type": file_type})
    await state.update_data(files=files)
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💾 Saqlash va davom etish", callback_data="admin_save_files")]
        ]
    )
    await message.answer(
        f"📎 Fayl muvaffaqiyatli qabul qilindi. (Jami: {len(files)} ta fayl)\n\n"
        f"Yana rasm yoki hujjat yuborishingiz mumkin. Barcha fayllarni yuborib bo'lgach, "
        f"quyidagi '💾 Saqlash va davom etish' tugmasini bosing:",
        reply_markup=kb
    )

@router.callback_query(TestCreationStates.waiting_for_file, F.data == "admin_save_files")
async def save_uploaded_files(call: CallbackQuery, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    files = data.get("files", [])
    if not files:
        await call.message.answer("⚠️ Iltimos, avval test savollari rasm yoki hujjat faylini yuboring!")
        return
        
    await state.set_state(TestCreationStates.waiting_for_keys)
    await call.message.answer("Javoblar kalitini yuboring (masalan, `abcdabcd...` yoki `1a2b3c...`):")

@router.message(TestCreationStates.waiting_for_keys)
async def process_test_keys(message: Message, state: FSMContext):
    raw_keys = message.text.strip().lower()
    if not raw_keys:
        await message.answer("Iltimos, matnli javoblar kalitini yuboring:")
        return
        
    # Standard clean up
    # If the user inputted numbered format (e.g. 1a2b3c...)
    # Let's extract only the letters
    import re
    cleaned = raw_keys.replace(" ", "").replace("\n", "")
    if any(char.isdigit() for char in cleaned):
        pairs = re.findall(r"(\d+)([a-d])", cleaned)
        if not pairs:
            await message.answer("⚠️ Kalit formati noto'g'ri. Masalan: `1a2b3c` formatida yoki shunchaki ketma-ket harflar `abcd` kiriting:")
            return
        # Find maximum question number
        max_num = max(int(num) for num, char in pairs)
        parsed = [""] * max_num
        for num_str, char in pairs:
            parsed[int(num_str) - 1] = char
        # Check if there are missing keys
        if "" in parsed:
            await message.answer("⚠️ Javoblarda ba'zi savol raqamlari tushib qolgan. Iltimos tekshirib qayta yuboring:")
            return
        answer_key = "".join(parsed)
    else:
        # Standard continuous string e.g. "abcdabcd"
        # Validate that it only contains a, b, c, d
        if not all(char in "abcd" for char in cleaned):
            await message.answer("⚠️ Kalit faqat a, b, c, d harflaridan iborat bo'lishi kerak. Qaytadan kiriting:")
            return
        answer_key = cleaned
        
    await state.update_data(answer_key=answer_key)
    await state.set_state(TestCreationStates.waiting_for_solutions)
    await message.answer(
        "Test yechimi (video link yoki tushuntirish matni) yuboring.\n"
        "Agar yechim bo'lmasa, `none` yuboring:"
    )

@router.message(TestCreationStates.waiting_for_solutions)
async def process_test_solutions(message: Message, state: FSMContext):
    solutions = message.text.strip()
    if not solutions:
        await message.answer("Iltimos, matn yuboring yoki `none` deb yozing:")
        return
        
    solutions_text = "" if solutions.lower() == "none" else solutions
    await state.update_data(solutions_text=solutions_text)
    
    # Next, ask which channel to assign
    admin_id = message.from_user.id
    channels = await get_channels_by_admin(admin_id)
    
    if not channels:
        await state.clear()
        kb = await get_admin_keyboard(admin_id)
        await message.answer(
            "⚠️ Sizda ulangan kanallar yo'q. Avval '🔗 Kanallar' bo'limida kanal qo'shing, keyin test yarating.",
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
    
    # Suggest UZB current time for reference
    uzb_now = datetime.datetime.utcnow() + datetime.timedelta(hours=5)
    await call.message.answer(
        f"Test boshlanish vaqtini kiriting.\n"
        f"Format: `YYYY-MM-DD HH:MM` (masalan, `2026-06-30 20:30`)\n\n"
        f"🕒 Hozirgi UZB vaqti: `{uzb_now.strftime('%Y-%m-%d %H:%M')}`",
        parse_mode="Markdown"
    )

@router.message(TestCreationStates.waiting_for_start_time)
async def process_test_start_time(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        # User enters local Uzbekistan time (UTC+5)
        local_dt = datetime.datetime.strptime(text, "%Y-%m-%d %H:%M")
        
        # Convert local time to UTC for storing & scheduling
        utc_dt = local_dt - datetime.timedelta(hours=5)
        
        # Check that the start time is not too far in the past
        if utc_dt < datetime.datetime.utcnow() - datetime.timedelta(minutes=5):
            await message.answer("⚠️ Boshlanish vaqti o'tib ketgan vaqt bo'la olmaydi. Kelajakdagi vaqtni kiriting:")
            return
    except ValueError:
        await message.answer("⚠️ Noto'g'ri format. Iltimos, `YYYY-MM-DD HH:MM` formatida kiriting (masalan, `2026-06-30 20:30`):")
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
    
    # Fetch details
    file_ids = data.get('files', [])
    answer_key = data['answer_key']
    solutions_text = data['solutions_text']
    channel_id = data['channel_id']
    start_time = datetime.datetime.fromisoformat(data['start_time'])
    
    # Save to DB
    success = await create_test(
        test_id=test_id,
        creator_id=admin_id,
        file_ids=file_ids,
        answer_key=answer_key,
        solutions_text=solutions_text,
        channel_id=channel_id,
        start_time=start_time,
        duration_minutes=duration
    )
    
    await state.clear()
    kb = await get_admin_keyboard(admin_id)
    
    if success:
        # Schedule the start and stop jobs
        await schedule_test_jobs(bot, test_id, start_time, duration)
        
        # Display UZB start time for reference
        local_start = start_time + datetime.timedelta(hours=5)
        await message.answer(
            f"🎉 **Test muvaffaqiyatli rejalashtirildi!**\n\n"
            f"📋 Test ID: `{test_id}`\n"
            f"📅 Boshlanishi: {local_start.strftime('%Y-%m-%d %H:%M')} (UZB)\n"
            f"⏱ Davomiyligi: {duration} daqiqa\n"
            f"🔑 Kalit: `{answer_key.upper()}`\n\n"
            f"Bot belgilangan vaqtda testni kanalga avtomatik joylashtiradi.",
            reply_markup=kb,
            parse_mode="Markdown"
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
        
    # Secure check: only creator or owner can delete
    if test.get("creator_id") != user_id and not await is_owner(user_id):
        await call.message.answer("⚠️ Siz ushbu testni o'chira olmaysiz.")
        return
        
    success = await delete_test(test_id)
    if success:
        # Also remove scheduled jobs from APScheduler if running
        try:
            from utils.scheduler import scheduler
            # Remove start and end jobs
            scheduler.remove_job(f"start_{test_id}")
            scheduler.remove_job(f"end_{test_id}")
        except Exception:
            pass
            
        await call.message.delete()
        await call.message.answer("✅ Test muvaffaqiyatli o'chirildi.")
    else:
        await call.message.answer("⚠️ Testni o'chirishda xatolik yuz berdi.")
