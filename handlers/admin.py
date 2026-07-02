import html
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import (
    is_admin, is_owner, get_total_users_count, get_registered_users_count, get_users_breakdown,
    get_total_tests_count, get_total_submissions_count, add_admin, remove_admin, get_all_admins,
    get_global_footer, set_global_footer, tests_col, submissions_col, users_col,
    add_mandatory_channel, remove_mandatory_channel, get_all_mandatory_channels, get_mandatory_channel,
    add_test_channel, remove_test_channel, get_all_test_channels, get_test_channels_by_admin, get_test_channel,
    add_genre, delete_genre, get_all_genres, test_channels_col
)
from states.states import AdminStates
from keyboards.reply import get_admin_keyboard, get_main_keyboard, get_cancel_keyboard
from keyboards.inline import (
    get_mandatory_channels_manage_keyboard, get_test_channels_manage_keyboard, get_genres_manage_keyboard
)
from config import OWNER_ID

logger = logging.getLogger(__name__)
router = Router()

# Admin check helper
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

@router.message(F.text == "⚙️ Admin panel")
async def open_admin_panel(message: Message):
    if not await check_admin_auth(message):
        return
    kb = await get_admin_keyboard(message.from_user.id)
    await message.answer("⚙️ Admin panelga xush kelibsiz. Quyidagi menyulardan birini tanlang:", reply_markup=kb)

@router.message(F.text == "🔙 Asosiy menyu")
async def back_to_main(message: Message):
    kb = await get_main_keyboard(message.from_user.id)
    await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=kb)

# --- Statistics Handler ---

@router.message(F.text == "📊 Statistika")
async def show_statistics(message: Message):
    if not await check_admin_auth(message):
        return
        
    user_id = message.from_user.id
    is_super = await is_owner(user_id)
    
    if is_super:
        tot_users = await get_total_users_count()
        reg_users = await get_registered_users_count()
        tot_tests = await get_total_tests_count()
        tot_subs = await get_total_submissions_count()
        breakdown = await get_users_breakdown()
        
        text = (
            f"📊 <b>Global Bot Statistikasi (Super Admin):</b>\n\n"
            f"👥 Jami foydalanuvchilar: <b>{tot_users}</b>\n"
            f"✅ Ro'yxatdan o'tganlar: <b>{reg_users}</b>\n"
            f"📝 Jami yaratilgan testlar: <b>{tot_tests}</b>\n"
            f"📥 Jami javob topshirganlar: <b>{tot_subs}</b>\n\n"
            f"📍 <b>Hududlar va Jins bo'yicha taqsimot:</b>\n"
        )
        if not breakdown:
            text += "Ma'lumotlar mavjud emas.\n"
        for region, data in breakdown.items():
            text += f"- {region}: <b>{data['Total']}</b> (🙋‍♂️ Erkak: {data.get('Male', 0)}, 🙋‍♀️ Ayol: {data.get('Female', 0)})\n"
            
        # Admin breakdown tracking
        text += "\n👮 <b>Adminlar faoliyati taqsimoti:</b>\n"
        admins = await get_all_admins()
        
        # Super admin activity
        owner_ch_count = await test_channels_col.count_documents({"added_by": OWNER_ID})
        owner_tests_count = await tests_col.count_documents({"creator_id": OWNER_ID})
        text += f"- Super Admin (ID: <code>{OWNER_ID}</code>):\n"
        text += f"  📢 Qo'shgan kanallari: <b>{owner_ch_count}</b>, Yaratgan testlari: <b>{owner_tests_count}</b>\n"
        
        for adm in admins:
            adm_id = adm["tg_id"]
            ch_count = await test_channels_col.count_documents({"added_by": adm_id})
            tests_count = await tests_col.count_documents({"creator_id": adm_id})
            text += f"- Admin (ID: <code>{adm_id}</code>):\n"
            text += f"  📢 Qo'shgan kanallari: <b>{ch_count}</b>, Yaratgan testlari: <b>{tests_count}</b>\n"
            
        await message.answer(text, parse_mode="HTML")
    else:
        personal_tests_count = await tests_col.count_documents({"creator_id": user_id})
        personal_ch_count = await test_channels_col.count_documents({"added_by": user_id})
        
        cursor = tests_col.find({"creator_id": user_id})
        admin_tests = await cursor.to_list(length=None)
        test_ids = [t["test_id"] for t in admin_tests]
        personal_subs_count = 0
        if test_ids:
            personal_subs_count = await submissions_col.count_documents({"test_id": {"$in": test_ids}})
            
        text = (
            f"📊 <b>Sizning Statistikangiz (Admin):</b>\n\n"
            f"📝 Yaratgan testlaringiz soni: <b>{personal_tests_count}</b>\n"
            f"📥 Testlaringizga yuborilgan jami javoblar: <b>{personal_subs_count}</b>\n"
            f"📢 Ulangan shaxsiy kanallaringiz: <b>{personal_ch_count}</b>\n"
        )
        await message.answer(text, parse_mode="HTML")

# --- Mandatory Subscriptions Panel (Super Admin Only) ---

@router.message(F.text == "🔗 Majburiy obunalar")
async def manage_mandatory_subs(message: Message):
    if not await check_owner_auth(message):
        return
    channels = await get_all_mandatory_channels()
    text = "🔗 <b>Majburiy obunalar (Global):</b>\n\n"
    if not channels:
        text += "Hozirda hech qanday majburiy kanal ulanmagan."
    else:
        for idx, ch in enumerate(channels, 1):
            status = "✅ Faol" if ch.get("is_active", True) else "❌ O'chirilgan"
            text += f"{idx}. <b>{ch['title']}</b> (ID: <code>{ch['channel_id']}</code>)\n   Holati: {status}\n\n"
            
    kb = get_mandatory_channels_manage_keyboard(channels)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "add_mchan")
async def start_add_mchan(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if not await is_owner(call.from_user.id):
        return
    await state.set_state(AdminStates.waiting_for_channel_id)
    cancel_kb = get_cancel_keyboard()
    await call.message.answer(
        "Majburiy kanal ID sini kiriting (masalan, `-100123456789`):\n\n"
        "💡 <b>Eslatma:</b> Bot ushbu kanalda administrator bo'lishi shart!",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )

@router.message(AdminStates.waiting_for_channel_id)
async def process_mchannel_id(message: Message, state: FSMContext):
    try:
        channel_id = int(message.text.strip())
        if not str(channel_id).startswith("-100"):
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Kanal ID noto'g'ri. U `-100` bilan boshlanishi kerak:")
        return
    try:
        member = await message.bot.get_chat_member(chat_id=channel_id, user_id=message.bot.id)
        if member.status not in ["administrator", "creator"]:
            await message.answer("⚠️ Bot ushbu kanalda administrator emas!")
            return
    except Exception as e:
        await message.answer(f"⚠️ Kanal topilmadi yoki bot u erda yo'q. Xatolik: {e}\nQaytadan kiriting:")
        return
    await state.update_data(channel_id=channel_id)
    await state.set_state(AdminStates.waiting_for_channel_link)
    await message.answer("Kanal taklif havolasini (invite link) kiriting:")

@router.message(AdminStates.waiting_for_channel_link)
async def process_mchannel_link(message: Message, state: FSMContext):
    link = message.text.strip()
    if not link.startswith("https://t.me/"):
        await message.answer("⚠️ Havola noto'g'ri formatda. `https://t.me/...` kabi havola yuboring:")
        return
    await state.update_data(invite_link=link)
    await state.set_state(AdminStates.waiting_for_channel_title)
    await message.answer("Kanal nomini kiriting:")

@router.message(AdminStates.waiting_for_channel_title)
async def process_mchannel_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Kanal nomini kiriting:")
        return
    data = await state.get_data()
    channel_id = data['channel_id']
    invite_link = data['invite_link']
    admin_id = message.from_user.id
    success = await add_mandatory_channel(channel_id, invite_link, title, admin_id)
    await state.clear()
    kb = await get_admin_keyboard(admin_id)
    if success:
        await message.answer(f"🎉 Majburiy kanal muvaffaqiyatli qo'shildi: <b>{html.escape(title)}</b>", reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer("⚠️ Kanal qo'shishda xatolik yuz berdi.", reply_markup=kb)

@router.callback_query(F.data.startswith("toggle_mchan:"))
async def process_toggle_mchan(call: CallbackQuery):
    await call.answer()
    if not await is_owner(call.from_user.id):
        return
    channel_id = int(call.data.split(":")[1])
    from database.db import toggle_mandatory_channel_status, get_all_mandatory_channels
    await toggle_mandatory_channel_status(channel_id)
    channels = await get_all_mandatory_channels()
    kb = get_mandatory_channels_manage_keyboard(channels)
    await call.message.edit_reply_markup(reply_markup=kb)

@router.callback_query(F.data.startswith("del_mchan:"))
async def process_delete_mchan(call: CallbackQuery):
    await call.answer()
    if not await is_owner(call.from_user.id):
        return
    channel_id = int(call.data.split(":")[1])
    await remove_mandatory_channel(channel_id)
    await call.message.delete()
    await call.message.answer("✅ Majburiy kanal o'chirildi.")


# --- Mening kanallarim Panel (Test channels managed per admin) ---

@router.message(F.text == "🔗 Mening kanallarim")
async def manage_my_test_channels(message: Message):
    if not await check_admin_auth(message):
        return
    user_id = message.from_user.id
    channels = await get_test_channels_by_admin(user_id)
    text = "🔗 <b>Test o'tkaziladigan kanallaringiz:</b>\n\n"
    if not channels:
        text += "Hozirda hech qanday test kanali ulamagansiz."
    else:
        for idx, ch in enumerate(channels, 1):
            text += f"{idx}. <b>{html.escape(ch['title'])}</b> (ID: <code>{ch['channel_id']}</code>)\n"
            
    kb = get_test_channels_manage_keyboard(channels)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "add_tchan")
async def start_add_tchan(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if not await is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.waiting_for_test_channel_id)
    cancel_kb = get_cancel_keyboard()
    await call.message.answer(
        "Test o'tkaziladigan kanal ID sini kiriting (masalan, `-100123456789`):\n\n"
        "💡 <b>Eslatma:</b> Bot ushbu kanalda administrator bo'lishi shart!",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )

@router.message(AdminStates.waiting_for_test_channel_id)
async def process_tchannel_id(message: Message, state: FSMContext):
    try:
        channel_id = int(message.text.strip())
        if not str(channel_id).startswith("-100"):
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Kanal ID noto'g'ri. U `-100` bilan boshlanishi kerak:")
        return
    try:
        member = await message.bot.get_chat_member(chat_id=channel_id, user_id=message.bot.id)
        if member.status not in ["administrator", "creator"]:
            await message.answer("⚠️ Bot ushbu kanalda administrator emas!")
            return
    except Exception as e:
        await message.answer(f"⚠️ Kanal topilmadi yoki bot u erda yo'q. Xatolik: {e}\nQaytadan kiriting:")
        return
    await state.update_data(channel_id=channel_id)
    await state.set_state(AdminStates.waiting_for_test_channel_link)
    await message.answer("Kanal taklif havolasini (invite link) kiriting:")

@router.message(AdminStates.waiting_for_test_channel_link)
async def process_tchannel_link(message: Message, state: FSMContext):
    link = message.text.strip()
    if not link.startswith("https://t.me/"):
        await message.answer("⚠️ Havola noto'g'ri formatda. `https://t.me/...` kabi havola yuboring:")
        return
    await state.update_data(invite_link=link)
    await state.set_state(AdminStates.waiting_for_test_channel_title)
    await message.answer("Kanal nomini kiriting:")

@router.message(AdminStates.waiting_for_test_channel_title)
async def process_tchannel_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Kanal nomini kiriting:")
        return
    data = await state.get_data()
    channel_id = data['channel_id']
    invite_link = data['invite_link']
    admin_id = message.from_user.id
    success = await add_test_channel(channel_id, invite_link, title, admin_id)
    await state.clear()
    kb = await get_admin_keyboard(admin_id)
    if success:
        await message.answer(f"🎉 Test o'tkaziladigan kanal muvaffaqiyatli qo'shildi: <b>{html.escape(title)}</b>", reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer("⚠️ Kanal qo'shishda xatolik yuz berdi.", reply_markup=kb)

@router.callback_query(F.data.startswith("del_tchan:"))
async def process_delete_tchan(call: CallbackQuery):
    await call.answer()
    user_id = call.from_user.id
    if not await is_admin(user_id):
        return
    channel_id = int(call.data.split(":")[1])
    channel = await get_test_channel(channel_id)
    if not channel:
        await call.message.answer("Kanal topilmadi.")
        return
    if channel.get("added_by") != user_id and not await is_owner(user_id):
        await call.message.answer("⚠️ Siz ushbu kanalni o'chira olmaysiz.")
        return
    success = await remove_test_channel(channel_id)
    if success:
        await call.message.delete()
        await call.message.answer("✅ Test kanali o'chirildi.")
    else:
        await call.message.answer("⚠️ Kanalni o'chirishda xatolik yuz berdi.")


# --- Genre Management Panel ---

@router.message(F.text == "📚 Janrlarni boshqarish")
async def manage_genres(message: Message):
    if not await check_admin_auth(message):
        return
    genres = await get_all_genres()
    text = "📚 <b>Janrlar ro'yxati:</b>\n\n"
    if not genres:
        text += "Hozircha hech qanday janr qo'shilmagan."
    else:
        for idx, g in enumerate(genres, 1):
            text += f"{idx}. <b>{html.escape(g['name'])}</b>\n"
            
    kb = get_genres_manage_keyboard(genres)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "add_genre")
async def start_add_genre(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if not await is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.waiting_for_genre_name)
    cancel_kb = get_cancel_keyboard()
    await call.message.answer("Yangi janr nomini kiriting:", reply_markup=cancel_kb)

@router.message(AdminStates.waiting_for_genre_name)
async def process_add_genre(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await state.clear()
        return
    name = message.text.strip()
    if not name:
        await message.answer("Iltimos, janr nomini kiriting:")
        return
    success = await add_genre(name, message.from_user.id)
    await state.clear()
    kb = await get_admin_keyboard(message.from_user.id)
    if success:
        await message.answer(f"🎉 Yangi janr muvaffaqiyatli qo'shildi: <b>{html.escape(name)}</b>", reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer("⚠️ Janr qo'shishda xatolik yuz berdi.", reply_markup=kb)

@router.callback_query(F.data.startswith("del_genre:"))
async def process_delete_genre(call: CallbackQuery):
    await call.answer()
    if not await is_admin(call.from_user.id):
        return
    genre_id = call.data.split(":")[1]
    success = await delete_genre(genre_id)
    if success:
        await call.message.delete()
        await call.message.answer("✅ Janr muvaffaqiyatli o'chirildi.")
    else:
        await call.message.answer("⚠️ Janrni o'chirishda xatolik yuz berdi.")


# --- Broadcast Handler (Super Admin Only) ---

@router.message(F.text == "📢 Xabar yuborish")
async def start_broadcast(message: Message, state: FSMContext):
    if not await check_owner_auth(message):
        return
        
    await state.set_state(AdminStates.waiting_for_broadcast_msg)
    cancel_kb = get_cancel_keyboard()
    await message.answer(
        "📢 <b>Xabar yuborish bo'limi.</b>\n\n"
        "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring (Matn, Rasm, Video yoki boshqa formatda):",
        reply_markup=cancel_kb,
        parse_mode="HTML"
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
        f"📢 <b>Xabar yuborish yakunlandi:</b>\n\n"
        f"✅ Muvaffaqiyatli: <b>{success}</b>\n"
        f"❌ Muvaffaqiyatsiz (bloklaganlar): <b>{fail}</b>",
        parse_mode="HTML"
    )


# --- Global Footer Settings (Super Admin Only) ---

@router.message(F.text == "🏷 Footer sozlamalari")
async def view_footer_settings(message: Message, state: FSMContext):
    if not await check_owner_auth(message):
        return
        
    footer = await get_global_footer()
    text = (
        f"🏷 <b>Universal Footer Sozlamalari</b>\n\n"
        f"Hozirgi footer matni:\n<code>{html.escape(footer or 'O‘rnatilmagan')}</code>\n\n"
        f"Yangi footer matnini yuboring. O'chirish uchun <code>none</code> so'zini yuboring:"
    )
    await state.set_state(AdminStates.waiting_for_footer_text)
    cancel_kb = get_cancel_keyboard()
    await message.answer(text, reply_markup=cancel_kb, parse_mode="HTML")

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
        await message.answer(f"✅ Yangi universal footer saqlandi:\n\n{html.escape(text)}", reply_markup=kb)


# --- Add/Remove Admins (Super Admin Only) ---

@router.message(F.text == "👮 Adminlarni boshqarish")
async def view_admins(message: Message):
    if not await check_owner_auth(message):
        return
        
    admins = await get_all_admins()
    text = "👮 <b>Standard Adminlar ro'yxati:</b>\n\n"
    if not admins:
        text += "Hozircha standard adminlar yo'q."
    else:
        for idx, adm in enumerate(admins, 1):
            text += f"{idx}. ID: <code>{adm['tg_id']}</code> (Qo'shilgan vaqti: {adm['added_at'].strftime('%Y-%m-%d %H:%M')})\n"
            
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Admin Qo'shish", callback_data="admin_add_new"),
                InlineKeyboardButton(text="🗑 Adminni O'chirish", callback_data="admin_remove_exist")
            ]
        ]
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

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
        await message.answer(f"✅ Foydalanuvchi (ID: <code>{tg_id}</code>) standard admin qilib tayinlandi.", reply_markup=kb, parse_mode="HTML")
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
