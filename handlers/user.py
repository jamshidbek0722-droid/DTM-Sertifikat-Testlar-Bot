from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, User, ReplyKeyboardRemove
from database.db import (
    get_user, create_user, register_user, is_admin, get_active_tests, get_past_tests, get_all_channels
)
from states.states import ProfileStates
from keyboards.reply import get_main_keyboard, get_cancel_keyboard
from keyboards.inline import (
    get_complete_profile_keyboard, get_gender_keyboard, get_subscription_keyboard,
    get_region_keyboard, get_subjects_keyboard
)
import logging

logger = logging.getLogger(__name__)
router = Router()

# We will import start_test_taking dynamically inside handlers to avoid circular imports.
# Alternatively, we can define a shared helper or import it directly.

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
            f"Assalomu alaykum, {name}! DTM Testlar botiga xush kelibsiz.\n\n"
            f"Bot imkoniyatlaridan to'liq foydalanish uchun profilingizni to'ldiring.",
            reply_markup=kb
        )
    else:
        kb = await get_main_keyboard(tg_id)
        await message.answer(
            f"Xush kelibsiz, {name}!",
            reply_markup=kb
        )

@router.message(F.text == "❌ Cancel")
async def process_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.clear()
    kb = await get_main_keyboard(message.from_user.id)
    await message.answer("Amal bekor qilindi.", reply_markup=kb)

# --- Profile Completion FSM ---

# --- Profile Completion FSM ---

@router.callback_query(F.data == "complete_profile")
async def start_profile_completion(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    
    await state.set_state(ProfileStates.waiting_for_region)
    # Clear reply keyboard
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
        f"Tanlangan hudud: **{region}**\n\nJinsingizni tanlang:",
        reply_markup=kb,
        parse_mode="Markdown"
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
    
    await state.update_data(gender=gender)
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
    
    # Initialize empty selected subjects
    await state.update_data(selected_subjects=[])
    kb = get_subjects_keyboard([])
    await message.answer(
        "Quyidagi ro'yxatdan qiziqadigan fanlaringizni tanlang (bir nechtasini tanlashingiz mumkin) "
        "va '💾 Saqlash' tugmasini bosing:",
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
        f"📚 Tanlangan fanlar: **{subject_str}**",
        reply_markup=kb,
        parse_mode="Markdown"
    )

# --- Main Menu Button Handlers ---

@router.message(F.text == "👤 Profile")
async def show_profile(message: Message):
    tg_id = message.from_user.id
    user = await get_user(tg_id)
    
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{tg_id}"
    
    if not user:
        user = await create_user(tg_id, message.from_user.full_name, message.from_user.username)
        
    if not user.get("registered", False):
        text = (
            f"👤 **Profilingiz**\n\n"
            f"🆔 ID: `{tg_id}`\n"
            f"📛 Ism: {user.get('name')}\n"
            f"🔗 Username: @{user.get('username') or 'yoq'}\n\n"
            f"⚠️ *Profil to'ldirilmagan!*"
        )
        kb = get_complete_profile_keyboard()
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")
    else:
        text = (
            f"👤 **Profilingiz**\n\n"
            f"🆔 ID: `{tg_id}`\n"
            f"📛 Ism: {user.get('name')}\n"
            f"🔗 Username: @{user.get('username') or 'yoq'}\n"
            f"📍 Hudud: {user.get('region')}\n"
            f"🙋‍♂️ Jins: {user.get('gender')}\n"
            f"🔢 Yosh: {user.get('age')}\n"
            f"📚 Qiziqish: {user.get('subject')}\n\n"
            f"👥 Taklif qilgan do'stlaringiz soni: **{user.get('referrals_count', 0)}**\n"
            f"🔗 Referral havolangiz:\n{ref_link}"
        )
        await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "📝 Active Tests")
async def show_active_tests(message: Message):
    tests = await get_active_tests()
    if not tests:
        await message.answer("Hozirda faol testlar mavjud emas.")
        return
        
    bot_info = await message.bot.get_me()
    text = "📝 **Faol testlar ro'yxati:**\n\n"
    for idx, t in enumerate(tests, 1):
        text += f"{idx}. Test ID: `{t['test_id']}`\n"
        text += f"⏱ Davomiyligi: {t['duration_minutes']} daqiqa\n"
        text += f"👉 [Testni boshlash (Deep-link)](https://t.me/{bot_info.username}?start=test_{t['test_id']})\n\n"
        
    await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True)

@router.message(F.text == "🗂 Past Tests")
async def show_past_tests(message: Message):
    tests = await get_past_tests()
    if not tests:
        await message.answer("Tugallangan testlar mavjud emas.")
        return
        
    text = "🗂 **Tugallangan testlar ro'yxati:**\n\n"
    for idx, t in enumerate(tests, 1):
        text += f"{idx}. Test ID: `{t['test_id']}`\n"
        text += f"🔑 Javoblar kaliti: `{t['answer_key'].upper()}`\n"
        if t.get('solutions_text'):
            text += f"💡 Yechim: {t['solutions_text']}\n"
        text += "\n"
        
    await message.answer(text, parse_mode="Markdown")

# --- Forced Subscription Callback Checker ---

@router.callback_query(F.data.startswith("check_sub:"))
async def check_sub_callback(call: CallbackQuery, state: FSMContext, bot: Bot):
    await call.answer()
    payload = call.data.split(":", 1)[1]
    
    # Run full subscription check
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
        # Prompt user again with the remaining channels and same payload
        await call.message.answer(
            "⚠️ Siz hali ham barcha kanallarga a'zo bo'lmadingiz. Iltimos, a'zo bo'lib qaytadan urinib ko'ring.",
            reply_markup=get_subscription_keyboard(unsubscribed, payload)
        )
        return
        
    # User is fully subscribed
    await call.message.delete()
    await call.message.answer("🎉 Tabriklaymiz! Kanallarga a'zo bo'lish muvaffaqiyatli tekshirildi.")
    
    if payload.startswith("test_"):
        test_id = payload.replace("test_", "")
        from handlers.test_taking import start_test_taking
        # Call start_test_taking directly
        await start_test_taking(call.message, call.from_user, test_id, state)
    else:
        kb = await get_main_keyboard(call.from_user.id)
        await call.message.answer("Siz asosiy menudasiz:", reply_markup=kb)
