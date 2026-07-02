import html
import datetime
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, User, ReplyKeyboardRemove
from database.db import (
    get_user, create_user, register_user, is_admin, get_active_tests, get_past_tests, get_all_channels,
    get_all_genres, get_genre, tests_col
)
from states.states import ProfileStates
from keyboards.reply import get_main_keyboard, get_cancel_keyboard
from keyboards.inline import (
    get_complete_profile_keyboard, get_gender_keyboard, get_subscription_keyboard,
    get_region_keyboard, get_subjects_keyboard, get_past_genres_keyboard, get_past_tests_keyboard
)
import logging

logger = logging.getLogger(__name__)
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    
    tg_id = message.from_user.id
    name = message.from_user.full_name
    username = message.from_user.username
    
    # Extract referral or deep link payload
    args = message.text.split()
    referred_by = None
    test_id = None
    
    if len(args) > 1:
        payload = args[1]
        if payload.startswith("ref_"):
            try:
                ref_id = int(payload.replace("ref_", ""))
                if ref_id != tg_id:
                    referred_by = ref_id
            except ValueError:
                pass
        elif payload.startswith("test_"):
            test_id = payload.replace("test_", "")

    # Create/Get User in Database
    user = await get_user(tg_id)
    if not user:
        user = await create_user(tg_id, name, username, referred_by)
        if referred_by:
            try:
                await bot.send_message(
                    chat_id=referred_by,
                    text=f"👤 Yangi foydalanuvchi taklif havolangiz orqali ro'yxatdan o'tdi!"
                )
            except Exception:
                pass
                
    # If the deep-link was for a test, forward immediately
    if test_id:
        from handlers.test_taking import start_test_taking
        await start_test_taking(message, message.from_user, test_id, state)
        return

    # Check if profile is fully registered
    if not user.get("registered", False):
        kb = get_complete_profile_keyboard()
        await message.answer(
            f"Assalomu alaykum, {html.escape(name)}! DTM Testlar botiga xush kelibsiz.\n\n"
            f"Bot imkoniyatlaridan to'liq foydalanish uchun profilingizni to'ldiring.",
            reply_markup=kb
        )
    else:
        kb = await get_main_keyboard(tg_id)
        await message.answer(
            f"Xush kelibsiz, {html.escape(name)}!",
            reply_markup=kb
        )

@router.message(F.text == "❌ Bekor qilish")
async def process_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.clear()
    kb = await get_main_keyboard(message.from_user.id)
    await message.answer("Amal bekor qilindi.", reply_markup=kb)

# --- Profile Completion FSM ---

@router.callback_query(F.data == "complete_profile")
async def start_profile_completion(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    
    await state.set_state(ProfileStates.waiting_for_region)
    cancel_kb = get_cancel_keyboard()
    await call.message.answer(
        "Ro'yxatdan o'tish boshlandi. Hududni tanlang:",
        reply_markup=cancel_kb
    )
    
    region_kb = get_region_keyboard()
    await call.message.answer(
        "Iltimos, yashash hududingizni (viloyat/shahar) tanlang:",
        reply_markup=region_kb
    )

@router.callback_query(ProfileStates.waiting_for_region, F.data.startswith("region:"))
async def process_region_callback(call: CallbackQuery, state: FSMContext):
    await call.answer()
    region = call.data.split(":")[1]
    
    await state.update_data(region=region)
    await state.set_state(ProfileStates.waiting_for_gender)
    
    kb = get_gender_keyboard()
    await call.message.answer(
        f"Tanlangan hudud: <b>{html.escape(region)}</b>\n\nJinsingizni tanlang:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await call.message.delete()

@router.message(ProfileStates.waiting_for_region)
async def process_region(message: Message, state: FSMContext):
    region = message.text.strip()
    if not region or len(region) < 3:
        await message.answer("Iltimos, hududingizni quyidagi tugmalar orqali tanlang:")
        return
        
    await state.update_data(region=region)
    await state.set_state(ProfileStates.waiting_for_gender)
    
    kb = get_gender_keyboard()
    await message.answer(
        "Jinsingizni tanlang:",
        reply_markup=kb
    )

@router.callback_query(ProfileStates.waiting_for_gender, F.data.startswith("gender_"))
async def process_gender(call: CallbackQuery, state: FSMContext):
    await call.answer()
    gender = call.data.split("_")[1]
    gender_uz = "Erkak" if gender == "Male" else "Ayol"
    
    await state.update_data(gender=gender_uz)
    await state.set_state(ProfileStates.waiting_for_age)
    
    await call.message.answer(
        "Yoshingizni kiriting (masalan, 18):"
    )

@router.message(ProfileStates.waiting_for_age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text.strip())
        if age < 5 or age > 100:
            raise ValueError
    except ValueError:
        await message.answer("Iltimos, yoshingizni to'g'ri raqamda kiriting (masalan, 18):")
        return
        
    await state.update_data(age=age)
    await state.set_state(ProfileStates.waiting_for_subject)
    
    await state.update_data(selected_subjects=[])
    kb = get_subjects_keyboard([])
    await message.answer(
        "Quyidagi ro'yxatdan qiziqadigan fanlaringizni tanlang (bir nechtasini tanlashingiz mumkin) "
        "va '📥 Saqlash' tugmasini bosing:",
        reply_markup=kb
    )

@router.callback_query(ProfileStates.waiting_for_subject, F.data.startswith("sub_toggle:"))
async def toggle_subject_callback(call: CallbackQuery, state: FSMContext):
    await call.answer()
    subject = call.data.split(":")[1]
    
    data = await state.get_data()
    selected_subjects = data.get("selected_subjects", [])
    
    if subject in selected_subjects:
        selected_subjects.remove(subject)
    else:
        selected_subjects.append(subject)
        
    await state.update_data(selected_subjects=selected_subjects)
    
    kb = get_subjects_keyboard(selected_subjects)
    await call.message.edit_reply_markup(reply_markup=kb)

@router.callback_query(ProfileStates.waiting_for_subject, F.data == "save_subjects")
async def save_subjects_callback(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_subjects = data.get("selected_subjects", [])
    
    if not selected_subjects:
        await call.answer("⚠️ Iltimos, kamida bitta fanni tanlang!", show_alert=True)
        return
        
    await call.answer()
    
    subject_str = ", ".join(selected_subjects)
    tg_id = call.from_user.id
    
    # Save user details
    await register_user(
        tg_id=tg_id,
        region=data['region'],
        gender=data['gender'],
        age=data['age'],
        subject=subject_str
    )
    
    await state.clear()
    kb = await get_main_keyboard(tg_id)
    await call.message.delete()
    await call.message.answer(
        f"🎉 Profilingiz muvaffaqiyatli yakunlandi! Rahmat.\n\n"
        f"📚 Tanlangan fanlar: <b>{html.escape(subject_str)}</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

# --- Main Menu Button Handlers ---

@router.message(F.text == "👤 Profil")
async def show_profile(message: Message):
    tg_id = message.from_user.id
    user = await get_user(tg_id)
    
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{tg_id}"
    
    if not user:
        user = await create_user(tg_id, message.from_user.full_name, message.from_user.username)
        
    if not user.get("registered", False):
        text = (
            f"👤 <b>Profilingiz</b>\n\n"
            f"🆔 ID: <code>{tg_id}</code>\n"
            f"📛 Ism: {html.escape(user.get('name', 'Yoq'))}\n"
            f"🔗 Username: @{html.escape(user.get('username') or 'yoq')}\n\n"
            f"⚠️ <i>Profil to'ldirilmagan!</i>"
        )
        kb = get_complete_profile_keyboard()
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        text = (
            f"👤 <b>Profilingiz</b>\n\n"
            f"🆔 ID: <code>{tg_id}</code>\n"
            f"📛 Ism: {html.escape(user.get('name', 'Yoq'))}\n"
            f"🔗 Username: @{html.escape(user.get('username') or 'yoq')}\n"
            f"📍 Hudud: {html.escape(user.get('region', 'Nomalum'))}\n"
            f"🙋‍♂️ Jins: {html.escape(user.get('gender', 'Nomalum'))}\n"
            f"🔢 Yosh: {user.get('age', 'Nomalum')}\n"
            f"📚 Qiziqish: {html.escape(user.get('subject', 'Nomalum'))}\n\n"
            f"👥 Taklif qilgan do'stlaringiz soni: <b>{user.get('referrals_count', 0)}</b>\n"
            f"🔗 Referral havolangiz:\n{ref_link}"
        )
        await message.answer(text, parse_mode="HTML")

@router.message(F.text == "📝 Faol testlar")
async def show_active_tests(message: Message):
    tests = await get_active_tests()
    if not tests:
        await message.answer("Hozirda faol testlar mavjud emas.")
        return
        
    bot_info = await message.bot.get_me()
    text = "📝 <b>Faol testlar ro'yxati:</b>\n\n"
    for idx, t in enumerate(tests, 1):
        text += f"{idx}. Test nomi: <b>{html.escape(t.get('test_name', 'Nomsiz test'))}</b>\n"
        text += f"   📋 Test ID: <code>{t['test_id']}</code>\n"
        text += f"   ⏱ Davomiyligi: {t['duration_minutes']} daqiqa\n"
        text += f"   👉 <a href='https://t.me/{bot_info.username}?start=test_{t['test_id']}'>Testni boshlash (Deep-link)</a>\n\n"
        
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)

# --- Completed Tests filtering by Genre & Deep Link (Item 8) ---

@router.message(F.text == "🗂 Yakunlangan testlar")
async def show_past_tests(message: Message):
    genres = await get_all_genres()
    if not genres:
        await message.answer("Tugallangan testlar mavjud emas (Hech qanday janr topilmadi).")
        return
        
    kb = get_past_genres_keyboard(genres)
    await message.answer("🗂 <b>Yakunlangan testlar bo'limi.</b>\nIltimos, test janrini tanlang:", reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("past_genre:"))
async def process_past_genre_select(call: CallbackQuery):
    await call.answer()
    genre_id = call.data.split(":")[1]
    
    # Query finished tests belonging to this genre
    cursor = tests_col.find({"status": "finished", "genre_id": genre_id})
    tests = await cursor.to_list(length=None)
    
    genre = await get_genre(genre_id)
    genre_name = genre["name"] if genre else "Nomalum"
    
    if not tests:
        await call.message.answer(f"⚠️ <b>{html.escape(genre_name)}</b> janrida yakunlangan testlar topilmadi.")
        return
        
    kb = get_past_tests_keyboard(tests)
    await call.message.answer(f"🗂 <b>{html.escape(genre_name)}</b> janridagi yakunlangan testlar:", reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("view_past_test:"))
async def process_view_past_test(call: CallbackQuery, bot: Bot):
    await call.answer()
    test_id = call.data.split(":")[1]
    
    from database.db import get_test
    test = await get_test(test_id)
    if not test:
        await call.message.answer("Test topilmadi.")
        return
        
    post_link = ""
    if test.get("test_post_msg_id") and test.get("channel_id"):
        ch_id = test["channel_id"]
        msg_id = test["test_post_msg_id"]
        try:
            chat = await bot.get_chat(ch_id)
            if chat.username:
                post_link = f"https://t.me/{chat.username}/{msg_id}"
            else:
                clean_id = str(ch_id).replace("-100", "")
                post_link = f"https://t.me/c/{clean_id}/{msg_id}"
        except Exception:
            clean_id = str(ch_id).replace("-100", "")
            post_link = f"https://t.me/c/{clean_id}/{msg_id}"
            
    local_start = test['start_time'] + datetime.timedelta(hours=5) if test.get("start_time") else datetime.datetime.now()
    
    text = (
        f"🗂 <b>YAKUNLANGAN TEST MA'LUMOTLARI</b>\n\n"
        f"📋 Test nomi: <b>{html.escape(test.get('test_name', 'Nomsiz'))}</b>\n"
        f"📋 Test ID: <code>{test_id}</code>\n"
        f"📅 Boshlangan vaqti: {local_start.strftime('%Y-%m-%d %H:%M')} (UZB)\n"
        f"🔑 Javoblar kaliti: <code>{test['answer_key'].upper()}</code>\n"
    )
    if test.get("solutions_text"):
        text += f"💡 Yechim: <i>{html.escape(test['solutions_text'])}</i>\n"
    if post_link:
        text += f"\n👉 <a href='{post_link}'>Original test postiga o'tish</a>"
        
    await call.message.answer(text, parse_mode="HTML")

# --- Forced Subscription Callback Checker ---

@router.callback_query(F.data.startswith("check_sub:"))
async def check_sub_callback(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()
    payload = call.data.split(":", 1)[1]
    
    channels = await get_all_channels()
    unsubscribed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch["channel_id"], user_id=call.from_user.id)
            if member.status in ["left", "kicked"]:
                unsubscribed.append(ch)
        except Exception:
            unsubscribed.append(ch)
            
    if unsubscribed:
        await call.message.answer(
            "⚠️ Siz hali ham barcha kanallarga a'zo bo'lmadingiz. Iltimos, a'zo bo'lib qaytadan urinib ko'ring.",
            reply_markup=get_subscription_keyboard(unsubscribed, payload)
        )
        return
        
    await call.message.delete()
    await call.message.answer("🎉 Tabriklaymiz! Kanallarga a'zo bo'lish muvaffaqiyatli tekshirildi.")
    
    if payload.startswith("test_"):
        test_id = payload.replace("test_", "")
        from handlers.test_taking import start_test_taking
        await start_test_taking(call.message, call.from_user, test_id, state)
    else:
        kb = await get_main_keyboard(call.from_user.id)
        await call.message.answer("Siz asosiy menudasiz:", reply_markup=kb)
