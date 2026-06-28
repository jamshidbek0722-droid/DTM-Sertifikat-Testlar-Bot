import uuid
import re
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

from middlewares.auth import AdminMiddleware
from keyboards.admin_kb import get_admin_main_kb, get_cancel_kb, get_confirm_kb, get_skip_kb, get_channels_kb
from database.repositories.test_repo import TestRepo
from database.repositories.channel_repo import ChannelRepo
from database.models import TestModel, TestStatus
from services.parser import parse_answer_string
from config import config
from utils.formatters import fmt

admin_router = Router()
admin_router.message.middleware(AdminMiddleware())
admin_router.callback_query.middleware(AdminMiddleware())

class TestUploadStates(StatesGroup):
    waiting_for_channel = State()
    waiting_for_title = State()
    waiting_for_subject = State()
    waiting_for_pdf = State()
    waiting_for_answer_key = State()
    waiting_for_solution_pdf = State()
    waiting_for_duration = State()
    confirm_upload = State()

@admin_router.message(Command("admin"))
async def cmd_admin(message: Message):
    await message.answer(fmt.ADMIN_PANEL, reply_markup=get_admin_main_kb())

@admin_router.callback_query(F.data == "admin_cancel")
async def cancel_action(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(fmt.CANCELLED)
    await call.message.answer(fmt.ADMIN_PANEL, reply_markup=get_admin_main_kb())
    await call.answer()

@admin_router.callback_query(F.data == "admin_upload_test")
async def start_upload(call: CallbackQuery, state: FSMContext):
    channels = await ChannelRepo.get_channels_by_admin(call.from_user.id)
    if not channels and call.from_user.id != config.owner_id:
        await call.message.edit_text("Sizga biriktirilgan kanallar yo'q.", reply_markup=get_cancel_kb())
        return
        
    # For testing, if super admin has no channels registered yet, let them use 0 or dummy
    if not channels and call.from_user.id == config.owner_id:
        channels = [type('obj', (object,), {'channel_id': 0, 'channel_username': 'Global'})()]
        
    await call.message.edit_text("Qaysi kanal uchun test yuklaysiz?", reply_markup=get_channels_kb(channels))
    await state.set_state(TestUploadStates.waiting_for_channel)
    await call.answer()

@admin_router.callback_query(TestUploadStates.waiting_for_channel, F.data.startswith("sel_chan_"))
async def process_channel_selection(call: CallbackQuery, state: FSMContext):
    channel_id = int(call.data.split("_")[2])
    await state.update_data(channel_id=channel_id)
    await call.message.edit_text(fmt.TEST_TITLE_PROMPT, reply_markup=get_cancel_kb())
    await state.set_state(TestUploadStates.waiting_for_title)
    await call.answer()

@admin_router.message(TestUploadStates.waiting_for_title)
async def process_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer(fmt.TEST_SUBJECT_PROMPT, reply_markup=get_cancel_kb())
    await state.set_state(TestUploadStates.waiting_for_subject)

@admin_router.message(TestUploadStates.waiting_for_subject)
async def process_subject(message: Message, state: FSMContext):
    await state.update_data(subject=message.text)
    await message.answer(fmt.TEST_PDF_PROMPT, reply_markup=get_cancel_kb())
    await state.set_state(TestUploadStates.waiting_for_pdf)

@admin_router.message(TestUploadStates.waiting_for_pdf, F.document)
async def process_pdf(message: Message, state: FSMContext):
    if not message.document.file_name.endswith('.pdf'):
        await message.answer(fmt.INVALID_INPUT + " (Faqat PDF)", reply_markup=get_cancel_kb())
        return
    await state.update_data(pdf_file_id=message.document.file_id)
    await message.answer(fmt.TEST_ANSWER_KEY_PROMPT, reply_markup=get_cancel_kb())
    await state.set_state(TestUploadStates.waiting_for_answer_key)

@admin_router.message(TestUploadStates.waiting_for_answer_key)
async def process_answer_key(message: Message, state: FSMContext):
    pattern = r"(\d+)[^0-9a-zA-Z]*([a-zA-Z])"
    matches = re.findall(pattern, message.text)
    if not matches:
        await message.answer(fmt.INVALID_INPUT, reply_markup=get_cancel_kb())
        return
        
    total_q = max(int(m[0]) for m in matches)
    res = parse_answer_string(message.text, total_q)
    
    if not res.is_valid:
        err_msg = fmt.PARSE_ERROR
        if res.invalid_options:
            err_msg += fmt.INVALID_OPTIONS.format(invalid_opts=", ".join(res.invalid_options))
        if res.duplicates:
            err_msg += fmt.DUPLICATE_ANSWERS.format(duplicates=", ".join(map(str, res.duplicates)))
        await message.answer(err_msg, reply_markup=get_cancel_kb())
        return
        
    await state.update_data(answer_key=res.parsed, total_questions=total_q)
    await message.answer(fmt.TEST_SOLUTION_PDF_PROMPT, reply_markup=get_skip_kb())
    await state.set_state(TestUploadStates.waiting_for_solution_pdf)

@admin_router.callback_query(TestUploadStates.waiting_for_solution_pdf, F.data == "admin_skip")
async def skip_solution(call: CallbackQuery, state: FSMContext):
    await state.update_data(solution_file_id=None)
    await call.message.edit_text(fmt.TEST_DURATION_PROMPT, reply_markup=get_cancel_kb())
    await state.set_state(TestUploadStates.waiting_for_duration)
    await call.answer()

@admin_router.message(TestUploadStates.waiting_for_solution_pdf, F.document)
async def process_solution(message: Message, state: FSMContext):
    if not message.document.file_name.endswith('.pdf'):
        await message.answer(fmt.INVALID_INPUT + " (Faqat PDF)", reply_markup=get_skip_kb())
        return
    await state.update_data(solution_file_id=message.document.file_id)
    await message.answer(fmt.TEST_DURATION_PROMPT, reply_markup=get_cancel_kb())
    await state.set_state(TestUploadStates.waiting_for_duration)

@admin_router.message(TestUploadStates.waiting_for_duration)
async def process_duration(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer(fmt.INVALID_INPUT, reply_markup=get_cancel_kb())
        return
    
    data = await state.get_data()
    data['duration'] = int(message.text)
    await state.update_data(duration=data['duration'])
    
    text = fmt.TEST_CONFIRM_PROMPT.format(
        title=data['title'],
        subject=data['subject'],
        total_q=data['total_questions'],
        duration=data['duration']
    )
    await message.answer(text, reply_markup=get_confirm_kb())
    await state.set_state(TestUploadStates.confirm_upload)

@admin_router.callback_query(TestUploadStates.confirm_upload, F.data == "admin_confirm_upload")
async def confirm_upload(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    # Forward to DB channel to get persistent file_id
    try:
        msg = await call.message.bot.send_document(
            chat_id=config.database_channel_id,
            document=data['pdf_file_id'],
            caption=f"Test: {data['title']}"
        )
        final_pdf_id = msg.document.file_id
        
        final_sol_id = None
        if data.get('solution_file_id'):
            sol_msg = await call.message.bot.send_document(
                chat_id=config.database_channel_id,
                document=data['solution_file_id'],
                caption=f"Solution: {data['title']}"
            )
            final_sol_id = sol_msg.document.file_id
    except Exception as e:
        await call.message.answer(f"Faylni bazaga yuklashda xatolik: {e}")
        return
        
    new_test = TestModel(
        test_id=str(uuid.uuid4()),
        title=data['title'],
        subject=data['subject'],
        channel_id=data['channel_id'],
        admin_id=call.from_user.id,
        pdf_file_id=final_pdf_id,
        answer_key=data['answer_key'],
        solution_file_id=final_sol_id,
        total_questions=data['total_questions'],
        duration=data['duration'],
        status=TestStatus.scheduled
    )
    
    await TestRepo.create_test(new_test)
    
    await call.message.edit_text(fmt.TEST_UPLOADED)
    await state.clear()
    await call.answer()
