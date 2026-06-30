from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import (
    is_admin, is_owner, get_total_users_count, get_registered_users_count, get_users_breakdown,
    get_total_tests_count, get_total_submissions_count, add_admin, remove_admin, get_all_admins,
    add_channel, remove_channel, get_channels_by_admin, get_all_channels, get_global_footer,
    set_global_footer, tests_col, submissions_col, users_col
)
from states.states import AdminStates
from keyboards.reply import get_admin_keyboard, get_main_keyboard, get_cancel_keyboard
import logging

logger = logging.getLogger(__name__)
router = Router()

# Admin check decorator or helper
async def check_admin_auth(message: Message) -> bool:
    if not await is_admin(message.from_user.id):
        await message.answer("⚠️ Sizda ushbu bo'limga kirish huquqi yo'q.")
        return False
    return True

async def check_owner_auth(message: Message) -> bool:
    if not await is_owner(message.from_user.id):
        await message.answer("⚠️ Bu amalni bajarish faqat Super Admin (Owner) uchun ruxsat etilgan.")
        return False
    return True

# --- Admin Menu Navigation ---

@router.message(F.text == "⚙️ Admin Panel")
async def open_admin_panel(message: Message):
    if not await check_admin_auth(message):
        return
    kb = await get_admin_keyboard(message.from_user.id)
    await message.answer("⚙️ Admin panelga xush kelibsiz. Quyidagi menyulardan birini tanlang:", reply_markup=kb)

@router.message(F.text == "🔙 Main Menu")
async def back_to_main(message: Message):
    kb = await get_main_keyboard(message.from_user.id)
    await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=kb)

# --- Statistics Handler ---

@router.message(F.text == "📊 Statistics")
async def show_statistics(message: Message):
    if not await check_admin_auth(message):
        return
        
    user_id = message.from_user.id
    is_super = await is_owner(user_id)
    
    if is_super:
        # Global Statistics for Super Admin
        tot_users = await get_total_users_count()
        reg_users = await get_registered_users_count()
        tot_tests = await get_total_tests_count()
        tot_subs = await get_total_submissions_count()
        breakdown = await get_users_breakdown()
        
        text = (
            f"📊 **Global Bot Statistikasi (Super Admin):**\n\n"
            f"👥 Jami foydalanuvchilar: **{tot_users}**\n"
            f"✅ Ro'yxatdan o'tganlar: **{reg_users}**\n"
            f"📝 Jami yaratilgan testlar: **{tot_tests}**\n"
            f"📥 Jami javob topshirganlar: **{tot_subs}**\n\n"
            f"📍 **Hududlar va Jins bo'yicha taqsimot:**\n"
        )
        if not breakdown:
            text += "Ma'lumotlar mavjud emas."
        for region, data in breakdown.items():
            text += f"- {region}: **{data['Total']}** (🙋‍♂️ Erkak: {data.get('Male', 0)}, 🙋‍♀️ Ayol: {data.get('Female', 0)})\n"
            
        await message.answer(text, parse_mode="Markdown")
    else:
        # Standard Admin Personal Stats
        # Get tests created by this admin
        cursor = tests_col.find({"creator_id": user_id})
        admin_tests = await cursor.to_list(length=None)
        test_ids = [t["test_id"] for t in admin_tests]
        
        personal_tests_count = len(admin_tests)
        personal_subs_count = 0
        if test_ids:
            personal_subs_count = await submissions_col.count_documents({"test_id": {"$in": test_ids}})
            
        # Get channels added by this admin
        personal_ch_count = len(await get_channels_by_admin(user_id))
        
        text = (
            f"📊 **Sizning Statistikangiz (Admin):**\n\n"
            f"📝 Yaratgan testlaringiz soni: **{personal_tests_count}**\n"
            f"📥 Testlaringizga yuborilgan jami javoblar: **{personal_subs_count}**\n"
            f"📢 Ulangan shaxsiy kanallaringiz: **{personal_ch_count}**\n"
        )
        await message.answer(text, parse_mode="Markdown")

# --- Mandatory Subs / My Channels Manager ---

@router.message(F.text.in_({"🔗 Mandatory Subs", "🔗 My Channels"}))
async def manage_channels(message: Message):
    if not await check_admin_auth(message):
        return
        
    user_id = message.from_user.id
    is_super = await is_owner(user_id)
    
    # Restrict Mandatory Subs button to super-admin and My Channels to standard-admin (for clean UI, but either gets their respective channels)
    if message.text == "🔗 Mandatory Subs" and not is_super:
        await message.answer("⚠️ Sizda bu bo'limga ruxsat yo'q.")
        return
        
    channels = await get_channels_by_admin(user_id)
    
    title_text = "🔗 **Siz ulagan kanallar:**\n\n" if not is_super else "🔗 **Majburiy a'zolik kanallari (Global):**\n\n"
    
    text = title_text
    if not channels:
        text += "Hozirda hech qanday kanal ulanmagan."
    else:
        for idx, ch in enumerate(channels, 1):
            text += f"{idx}. **{ch['title']}** (ID: `{ch['channel_id']}`)\n   🔗 Havola: {ch['invite_link']}\n"
            if is_super:
                text += f"   👮 Qo'shdi: Admin ID `{ch.get('added_by', 'Owner')}`\n"
            text += "\n"
            
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Kanal Qo'shish", callback_data="admin_add_channel"),
                InlineKeyboardButton(text="🗑 Kanalni O'chirish", callback_data="admin_remove_channel")
            ]
        ]
    )
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "admin_add_channel")
async def start_add_channel(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if not await is_admin(call.from_user.id):
        return
        
    await state.set_state(AdminStates.waiting_for_channel_id)
    cancel_kb = get_cancel_keyboard()
    await call.message.answer(
        "Kanal ID sini kiriting (masalan, `-100123456789`):\n\n"
        "💡 *Eslatma:* Bot ushbu kanalda administrator bo'lishi shart!",
        reply_markup=cancel_kb,
        parse_mode="Markdown"
    )

@router.message(AdminStates.waiting_for_channel_id)
async def process_channel_id(message: Message, state: FSMContext):
    try:
        channel_id = int(message.text.strip())
        if not str(channel_id).startswith("-100"):
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Kanal ID noto'g'ri. U `-100` bilan boshlanishi kerak (masalan, `-100123456789`):")
        return
        
    # Verify bot is administrator in this channel
    try:
        member = await message.bot.get_chat_member(chat_id=channel_id, user_id=message.bot.id)
        if member.status not in ["administrator", "creator"]:
            await message.answer("⚠️ Bot ushbu kanalda administrator emas! Botni administrator qilib qaytadan urinib ko'ring:")
            return
    except Exception as e:
        await message.answer(f"⚠️ Kanal topilmadi yoki bot u erda yo'q. Xatolik: {e}\nQaytadan kiriting:")
        return
        
    await state.update_data(channel_id=channel_id)
    await state.set_state(AdminStates.waiting_for_channel_link)
    await message.answer("Kanalga taklif havolasini (invite link) kiriting:")

@router.message(AdminStates.waiting_for_channel_link)
async def process_channel_link(message: Message, state: FSMContext):
    link = message.text.strip()
    if not link.startswith("https://t.me/"):
        await message.answer("⚠️ Havola noto'g'ri formatda. `https://t.me/...` kabi havola yuboring:")
        return
        
    await state.update_data(invite_link=link)
    await state.set_state(AdminStates.waiting_for_channel_title)
    await message.answer("Kanal nomini kiriting:")

@router.message(AdminStates.waiting_for_channel_title)
async def process_channel_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Kanal nomini kiriting:")
        return
        
    data = await state.get_data()
    channel_id = data['channel_id']
    invite_link = data['invite_link']
    admin_id = message.from_user.id
    
    success = await add_channel(
        channel_id=channel_id,
        invite_link=invite_link,
        title=title,
        added_by=admin_id
    )
    
    await state.clear()
    kb = await get_admin_keyboard(admin_id)
    if success:
        await message.answer(f"🎉 Kanal muvaffaqiyatli qo'shildi: **{title}**", reply_markup=kb, parse_mode="Markdown")
    else:
        await message.answer("⚠️ Kanal qo'shishda xatolik yuz berdi.", reply_markup=kb)

@router.callback_query(F.data == "admin_remove_channel")
async def start_remove_channel(call: CallbackQuery):
    await call.answer()
    user_id = call.from_user.id
    if not await is_admin(user_id):
        return
        
    channels = await get_channels_by_admin(user_id)
    if not channels:
        await call.message.answer("O'chirish uchun ulangan kanallar topilmadi.")
        return
        
    buttons = []
    for ch in channels:
        buttons.append([InlineKeyboardButton(text=f"🗑 {ch['title']}", callback_data=f"del_chan:{ch['channel_id']}")])
        
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await call.message.answer("O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=kb)

@router.callback_query(F.data.startswith("del_chan:"))
async def process_delete_channel(call: CallbackQuery):
    await call.answer()
    user_id = call.from_user.id
    if not await is_admin(user_id):
        return
        
    channel_id = int(call.data.split(":")[1])
    
    # Secure: non-owners can only delete their own channels
    channel = await channels_col.find_one({"channel_id": channel_id})
    if not channel:
        await call.message.answer("Kanal topilmadi.")
        return
        
    if channel.get("added_by") != user_id and not await is_owner(user_id):
        await call.message.answer("⚠️ Siz ushbu kanalni o'chira olmaysiz.")
        return
        
    success = await remove_channel(channel_id)
    if success:
        await call.message.delete()
        await call.message.answer("✅ Kanal muvaffaqiyatli o'chirildi.")
    else:
        await call.message.answer("⚠️ Kanalni o'chirishda xatolik yuz berdi.")

# --- Broadcast Handler (Super Admin Only) ---

@router.message(F.text == "📢 Broadcast")
async def start_broadcast(message: Message, state: FSMContext):
    if not await check_owner_auth(message):
        return
        
    await state.set_state(AdminStates.waiting_for_broadcast_msg)
    cancel_kb = get_cancel_keyboard()
    await message.answer(
        "📢 **Xabar yuborish bo'limi.**\n\n"
        "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring (Matn, Rasm, Video yoki boshqa formatda):",
        reply_markup=cancel_kb,
        parse_mode="Markdown"
    )

@router.message(AdminStates.waiting_for_broadcast_msg)
async def process_broadcast_message(message: Message, state: FSMContext, bot: Bot):
    if not await is_owner(message.from_user.id):
        await state.clear()
        return
        
    await state.clear()
    kb = await get_admin_keyboard(message.from_user.id)
    
    status_msg = await message.answer("🔄 Xabar barcha foydalanuvchilarga yuborilmoqda. Iltimos kuting...", reply_markup=kb)
    
    success = 0
    fail = 0
    
    # Cursor to loop through all users
    cursor = users_col.find({})
    async for user in cursor:
        tg_id = user["tg_id"]
        try:
            await bot.copy_message(
                chat_id=tg_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            success += 1
        except Exception:
            fail += 1
            
    await status_msg.delete()
    await message.answer(
        f"📢 **Xabar yuborish yakunlandi:**\n\n"
        f"✅ Muvaffaqiyatli: **{success}**\n"
        f"❌ Muvaffaqiyatsiz (bloklaganlar): **{fail}**",
        parse_mode="Markdown"
    )

# --- Global Footer Settings (Super Admin Only) ---

@router.message(F.text == "🏷 Footer Settings")
async def view_footer_settings(message: Message, state: FSMContext):
    if not await check_owner_auth(message):
        return
        
    footer = await get_global_footer()
    text = (
        f"🏷 **Universal Footer Sozlamalari**\n\n"
        f"Hozirgi footer matni:\n`{footer or 'O‘rnatilmagan'}`\n\n"
        f"Yangi footer matnini yuboring. O'chirish uchun `none` so'zini yuboring:"
    )
    await state.set_state(AdminStates.waiting_for_footer_text)
    cancel_kb = get_cancel_keyboard()
    await message.answer(text, reply_markup=cancel_kb, parse_mode="Markdown")

@router.message(AdminStates.waiting_for_footer_text)
async def process_footer_text(message: Message, state: FSMContext):
    if not await is_owner(message.from_user.id):
        await state.clear()
        return
        
    text = message.text.strip()
    await state.clear()
    
    kb = await get_admin_keyboard(message.from_user.id)
    if text.lower() == "none":
        await set_global_footer("")
        await message.answer("✅ Universal footer o'chirildi.", reply_markup=kb)
    else:
        await set_global_footer(text)
        await message.answer(f"✅ Yangi universal footer saqlandi:\n\n{text}", reply_markup=kb)

# --- Add/Remove Admins (Super Admin Only) ---

@router.message(F.text == "👮 Add/Remove Admins")
async def view_admins(message: Message):
    if not await check_owner_auth(message):
        return
        
    admins = await get_all_admins()
    text = "👮 **Standard Adminlar ro'yxati:**\n\n"
    if not admins:
        text += "Hozircha standard adminlar yo'q."
    else:
        for idx, adm in enumerate(admins, 1):
            text += f"{idx}. ID: `{adm['tg_id']}` (Qo'shilgan vaqti: {adm['added_at'].strftime('%Y-%m-%d %H:%M')})\n"
            
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Admin Qo'shish", callback_data="admin_add_new"),
                InlineKeyboardButton(text="🗑 Adminni O'chirish", callback_data="admin_remove_exist")
            ]
        ]
    )
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "admin_add_new")
async def start_add_admin(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if not await is_owner(call.from_user.id):
        return
        
    await state.set_state(AdminStates.waiting_for_admin_id_to_add)
    cancel_kb = get_cancel_keyboard()
    await call.message.answer("Yangi adminning Telegram ID sini kiriting:", reply_markup=cancel_kb)

@router.message(AdminStates.waiting_for_admin_id_to_add)
async def process_add_admin(message: Message, state: FSMContext):
    if not await is_owner(message.from_user.id):
        await state.clear()
        return
        
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Telegram ID faqat raqamlardan iborat bo'lishi kerak. Qaytadan kiriting:")
        return
        
    success = await add_admin(tg_id, message.from_user.id)
    await state.clear()
    kb = await get_admin_keyboard(message.from_user.id)
    
    if success:
        await message.answer(f"✅ Foydalanuvchi (ID: `{tg_id}`) standard admin qilib tayinlandi.", reply_markup=kb, parse_mode="Markdown")
    else:
        await message.answer("⚠️ Ushbu foydalanuvchi allaqachon admin yoki xatolik yuz berdi.", reply_markup=kb)

@router.callback_query(F.data == "admin_remove_exist")
async def start_remove_admin(call: CallbackQuery):
    await call.answer()
    if not await is_owner(call.from_user.id):
        return
        
    admins = await get_all_admins()
    if not admins:
        await call.message.answer("O'chirish uchun adminlar mavjud emas.")
        return
        
    buttons = []
    for adm in admins:
        buttons.append([InlineKeyboardButton(text=f"🗑 ID: {adm['tg_id']}", callback_data=f"del_adm:{adm['tg_id']}")])
        
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await call.message.answer("O'chirmoqchi bo'lgan adminni tanlang:", reply_markup=kb)

@router.callback_query(F.data.startswith("del_adm:"))
async def process_delete_admin(call: CallbackQuery):
    await call.answer()
    if not await is_owner(call.from_user.id):
        return
        
    tg_id = int(call.data.split(":")[1])
    success = await remove_admin(tg_id)
    
    if success:
        await call.message.delete()
        await call.message.answer("✅ Admin muvaffaqiyatli o'chirildi.")
    else:
        await call.message.answer("⚠️ Adminni o'chirishda xatolik yuz berdi.")
