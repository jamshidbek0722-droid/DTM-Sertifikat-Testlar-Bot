import uuid
import datetime
from datetime import timezone
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from database.connection import db_conn
from database.repositories.test_repo import TestRepo
from database.repositories.user_repo import UserRepo
from database.repositories.submission_repo import SubmissionRepo
from database.models import UserModel, SubmissionModel, TestStatus, TestModel
from services.parser import parse_answer_string
from services.grader import grade_submission
from keyboards.user_kb import get_join_test_kb
from utils.formatters import fmt

user_router = Router()

@user_router.message(Command("start"))
async def cmd_start(message: Message):
    user = UserModel(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name
    )
    await UserRepo.create_user(user)
        
    await message.answer(fmt.WELCOME.format(name=message.from_user.full_name))

@user_router.message(Command("test"))
async def cmd_test(message: Message):
    await message.answer("Testlar ro'yxati kanal orqali yuboriladi. Kanalga kiring va 'Ishtirok etish' tugmasini bosing.")

@user_router.callback_query(F.data.startswith("join_test_"))
async def join_test(call: CallbackQuery):
    test_id = call.data.split("_")[2]
    test = await TestRepo.get_test_by_id(test_id)
    
    if not test or test.status != TestStatus.active:
        await call.answer("Bu test faol emas yoki yakunlangan.", show_alert=True)
        return
        
    sub = await SubmissionRepo.get_submission(test_id, call.from_user.id)
    if sub:
        await call.answer(fmt.TEST_ALREADY_SUBMITTED, show_alert=True)
        return
        
    await call.message.bot.send_document(
        chat_id=call.from_user.id,
        document=test.pdf_file_id,
        caption=fmt.TEST_JOIN_SUCCESS
    )
    await call.answer()

@user_router.message(F.text)
async def process_submission(message: Message):
    active_tests = await db_conn.db.tests.find({"status": TestStatus.active.value}).to_list(length=10)
    active_test_models = [TestModel(**doc) for doc in active_tests]
    
    if not active_test_models:
        return 
        
    target_test = None
    for t in active_test_models:
        sub = await SubmissionRepo.get_submission(t.test_id, message.from_user.id)
        if not sub:
            target_test = t
            break
            
    if not target_test:
        return

    res = parse_answer_string(message.text, target_test.total_questions)
    
    if not res.parsed and len(res.invalid_options) == 0:
        return 
        
    if not res.is_valid:
        err_msg = fmt.PARSE_ERROR
        if res.missing:
            err_msg += fmt.MISSING_ANSWERS.format(missing=", ".join(map(str, res.missing)))
        if res.invalid_options:
            err_msg += fmt.INVALID_OPTIONS.format(invalid_opts=", ".join(res.invalid_options))
        if res.duplicates:
            err_msg += fmt.DUPLICATE_ANSWERS.format(duplicates=", ".join(map(str, res.duplicates)))
        await message.answer(err_msg)
        return
        
    score, pct, breakdown = await grade_submission(res.parsed, target_test.answer_key, target_test.total_questions)
    
    now = datetime.datetime.now(timezone.utc)
    is_late = False
    if target_test.end_time and now > target_test.end_time:
        is_late = True
        
    sub = SubmissionModel(
        submission_id=str(uuid.uuid4()),
        test_id=target_test.test_id,
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        raw_answer_string=message.text,
        parsed_answers=res.parsed,
        score=score,
        percentage=pct,
        is_late=is_late
    )
    await SubmissionRepo.create_submission(sub)
    
    if not is_late:
        await UserRepo.increment_stats(message.from_user.id, score)
    
    if is_late:
        await message.answer("Javobingiz qabul qilindi, lekin vaqt tugagani uchun reytingga qo'shilmaydi.")
    else:
        await message.answer(fmt.SUBMIT_SUCCESS.format(score=score, total=target_test.total_questions, percentage=pct))
