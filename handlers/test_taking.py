import datetime
import html
import re
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, User
from database.db import get_test, get_submission, create_submission, get_global_footer
from states.states import TestTakingStates
from keyboards.reply import get_main_keyboard, get_cancel_keyboard
import logging

logger = logging.getLogger(__name__)
router = Router()

def parse_answer_key_to_dict(answer_key: str) -> dict:
    """
    Parses answer key (e.g., '31a32b33c' or 'abcd') to a dict of {question_number: letter}.
    """
    cleaned = answer_key.strip().lower().replace(" ", "").replace("\n", "")
    if any(char.isdigit() for char in cleaned):
        pairs = re.findall(r"(\d+)([a-d])", cleaned)
        return {int(num): char for num, char in pairs}
    else:
        return {i: char for i, char in enumerate(cleaned, start=1)}

def parse_user_answers(user_input: str, correct_dict: dict) -> dict:
    """
    Parses user answers and returns a dict of {question_number: letter}.
    If the input contains no numbers (e.g., "abc"), maps them sequentially
    to the sorted list of question numbers from correct_dict.
    """
    cleaned = user_input.lower().replace(" ", "").replace("\n", "").replace(",", "").replace("\r", "")
    
    if any(char.isdigit() for char in cleaned):
        pairs = re.findall(r"(\d+)\s*[-:)]?\s*([a-d])", cleaned)
        return {int(num): char for num, char in pairs}
    else:
        sorted_nums = sorted(correct_dict.keys())
        user_dict = {}
        letters = [c for c in cleaned if c in "abcd"]
        for idx, num in enumerate(sorted_nums):
            if idx < len(letters):
                user_dict[num] = letters[idx]
        return user_dict

async def start_test_taking(message: Message, user: User, test_id: str, state: FSMContext):
    await state.clear()
    
    test = await get_test(test_id)
    if not test:
        await message.answer("⚠️ Kechirasiz, bunday test topilmadi.")
        return
        
    status = test.get("status", "scheduled")
    if status == "scheduled":
        await message.answer("⚠️ Ushbu test hali boshlanmagan. Iltimos, test boshlanishini kuting.")
        return
    elif status == "finished":
        await message.answer("⚠️ Ushbu test yakunlangan va javoblar qabul qilinmaydi.")
        return
        
    # Check if user already submitted answers
    submission = await get_submission(user.id, test_id)
    if submission:
        await message.answer("⚠️ Siz ushbu testga javob topshirib bo'lgansiz. Qayta topshirish taqiqlanadi.")
        return
        
    correct_dict = parse_answer_key_to_dict(test['answer_key'])
    
    # Start FSM state
    await state.set_state(TestTakingStates.waiting_for_answers)
    await state.update_data(
        test_id=test_id,
        started_at=datetime.datetime.utcnow().isoformat()
    )
    
    cancel_kb = get_cancel_keyboard()
    start_num = min(correct_dict.keys())
    await message.answer(
        f"📝 <b>Test boshlandi!</b>\n\n"
        f"Test nomi: <b>{html.escape(test.get('test_name', 'Nomsiz test'))}</b>\n"
        f"Test ID: <code>{test_id}</code>\n"
        f"Savollar soni: {len(correct_dict)}\n"
        f"Davomiyligi: {test['duration_minutes']} daqiqa\n\n"
        f"Quyida test savollari fayli yuborilmoqda. Javoblarni quyidagi formatda yuboring:\n"
        f"👉 <code>abcd...</code> (masalan, <code>abcdabcd...</code> yoki <code>{start_num}a{start_num+1}b...</code>)",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )
    
    # Send test files
    file_ids = test.get("file_ids", [])
    if not file_ids and test.get("file_id"):
        file_ids = [{"file_id": test.get("file_id"), "file_type": test.get("file_type", "document")}]
        
    for item in file_ids:
        f_id = item.get("file_id")
        f_type = item.get("file_type", "document")
        try:
            if f_type == "photo":
                await message.bot.send_photo(chat_id=user.id, photo=f_id, caption="📊 Test savollari")
            else:
                await message.bot.send_document(chat_id=user.id, document=f_id, caption="📊 Test savollari")
        except Exception as e:
            logger.error(f"Error sending test file {f_id} to user {user.id}: {e}")
            await message.answer("⚠️ Test savollari faylini yuborishda xatolik yuz berdi, lekin javoblaringizni yuborishingiz mumkin.")

@router.message(TestTakingStates.waiting_for_answers)
async def process_test_answers(message: Message, state: FSMContext):
    user_input = message.text
    if not user_input:
        await message.answer("Iltimos, javoblarni matn shaklida yuboring.")
        return
        
    data = await state.get_data()
    test_id = data.get("test_id")
    started_at_str = data.get("started_at")
    
    test = await get_test(test_id)
    if not test:
        await state.clear()
        kb = await get_main_keyboard(message.from_user.id)
        await message.answer("⚠️ Xatolik: Test topilmadi.", reply_markup=kb)
        return
        
    # Check if test has finished in the meantime
    if test.get("status") == "finished":
        await state.clear()
        kb = await get_main_keyboard(message.from_user.id)
        await message.answer("⚠️ Kechirasiz, ushbu test uchun vaqt tugadi va javoblar qabul qilinishi to'xtatildi.", reply_markup=kb)
        return
        
    correct_dict = parse_answer_key_to_dict(test['answer_key'])
    user_dict = parse_user_answers(user_input, correct_dict)
    
    total_questions = len(correct_dict)
    expected_nums = set(correct_dict.keys())
    user_answered_nums = set(user_dict.keys())
    
    # Validation: if length doesn't match total questions or numbers don't match
    if len(user_dict) != total_questions or not expected_nums.issubset(user_answered_nums):
        await message.answer(
            f"⚠️ <b>Xatolik:</b> Siz yuborgan javoblar soni yoki tartibi mos kelmadi.\n"
            f"Kutilayotgan savollar oralig'i: <b>{min(expected_nums)}-{max(expected_nums)}</b> ({total_questions} ta savol)\n"
            f"Siz yuborganingiz: {len(user_dict)} ta savol\n\n"
            f"Iltimos, qaytadan tekshirib, to'liq javob yuboring."
        )
        return
        
    # Calculate scores
    correct_count = 0
    for num, correct_char in correct_dict.items():
        if user_dict.get(num) == correct_char:
            correct_count += 1
            
    score = round((correct_count / total_questions) * 100, 2)
    
    # Calculate duration
    started_at = datetime.datetime.fromisoformat(started_at_str)
    duration = datetime.datetime.utcnow() - started_at
    time_taken_seconds = int(duration.total_seconds())
    
    # Format answers string for saving
    user_answers_str = "".join(f"{num}{char}" for num, char in sorted(user_dict.items()))
    
    # Save submission
    success = await create_submission(
        user_id=message.from_user.id,
        test_id=test_id,
        answers=user_answers_str,
        score=score,
        correct_count=correct_count,
        total_count=total_questions,
        time_taken_seconds=time_taken_seconds
    )
    
    await state.clear()
    kb = await get_main_keyboard(message.from_user.id)
    
    footer = await get_global_footer()
    footer_text = f"\n\n{footer}" if footer else ""
    
    # Format duration
    mins = time_taken_seconds // 60
    secs = time_taken_seconds % 60
    time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
    
    await message.answer(
        f"✅ <b>Javoblaringiz qabul qilindi!</b>\n\n"
        f"📋 Test ID: <code>{test_id}</code>\n"
        f"📊 Natijangiz: <b>{score}%</b>\n"
        f"✅ To'g'ri javoblar: {correct_count}/{total_questions}\n"
        f"⏱ Sarflangan vaqt: {time_str}{footer_text}",
        reply_markup=kb,
        parse_mode="HTML"
    )
