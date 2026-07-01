import datetime
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, User
from database.db import get_test, get_submission, create_submission, get_global_footer
from states.states import TestTakingStates
from keyboards.reply import get_main_keyboard, get_cancel_keyboard
import logging

logger = logging.getLogger(__name__)
router = Router()

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
        
    # Start FSM state
    await state.set_state(TestTakingStates.waiting_for_answers)
    await state.update_data(
        test_id=test_id,
        started_at=datetime.datetime.utcnow().isoformat()
    )
    
    cancel_kb = get_cancel_keyboard()
    await message.answer(
        f"📝 **Test boshlandi!**\n\n"
        f"Test ID: `{test_id}`\n"
        f"Savollar soni: {len(test['answer_key'])}\n"
        f"Davomiyligi: {test['duration_minutes']} daqiqa\n\n"
        f"Quyida test savollari fayli yuborilmoqda. Javoblarni quyidagi formatda yuboring:\n"
        f"👉 `abcd...` (masalan, `abcdabcd...` yoki `1a2b3c...`)",
        reply_markup=cancel_kb,
        parse_mode="Markdown"
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

def parse_answers(user_input: str, total_questions: int) -> str:
    """
    Cleans and parses user input.
    Supports continuous letters (abcd...) or numbered format (1a2b3c...).
    Returns a cleaned string of answers.
    """
    cleaned = user_input.replace(" ", "").replace("\n", "").lower()
    
    # If the user inputted numbered format (e.g. 1a2b3c...)
    # Let's extract only the letters
    if any(char.isdigit() for char in cleaned):
        parsed = [""] * total_questions
        import re
        # Find all patterns of number+letter (e.g., 1a, 2b, 12c)
        pairs = re.findall(r"(\d+)([a-d])", cleaned)
        for num_str, char in pairs:
            idx = int(num_str) - 1
            if 0 <= idx < total_questions:
                parsed[idx] = char
        return "".join(parsed)
    
    return cleaned

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
        
    total_questions = len(test['answer_key'])
    answers = parse_answers(user_input, total_questions)
    
    # Validation: if length doesn't match total questions
    if len(answers) != total_questions or "" in answers:
        # Check raw input length vs expected length
        await message.answer(
            f"⚠️ **Xatolik:** Siz yuborgan javoblar soni mos kelmadi.\n"
            f"Kutilayotgan savollar soni: {total_questions}\n"
            f"Siz yuborganingiz: {len(answers)}\n\n"
            f"Iltimos, qaytadan tekshirib, to'liq va faqat `a, b, c, d` harflaridan iborat javoblarni yuboring."
        )
        return
        
    # Calculate scores
    correct_key = test['answer_key']
    correct_count = 0
    for i in range(total_questions):
        if answers[i] == correct_key[i]:
            correct_count += 1
            
    score = round((correct_count / total_questions) * 100, 2)
    
    # Calculate duration
    started_at = datetime.datetime.fromisoformat(started_at_str)
    duration = datetime.datetime.utcnow() - started_at
    time_taken_seconds = int(duration.total_seconds())
    
    # Save submission
    success = await create_submission(
        user_id=message.from_user.id,
        test_id=test_id,
        answers=answers,
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
        f"✅ **Javoblaringiz qabul qilindi!**\n\n"
        f"📋 Test ID: `{test_id}`\n"
        f"📊 Natijangiz: **{score}%**\n"
        f"✅ To'g'ri javoblar: {correct_count}/{total_questions}\n"
        f"⏱ Sarflangan vaqt: {time_str}{footer_text}",
        reply_markup=kb,
        parse_mode="Markdown"
    )
