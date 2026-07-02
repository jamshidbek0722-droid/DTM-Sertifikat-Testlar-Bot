from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from database.db import is_admin, is_owner

async def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📝 Faol testlar"), KeyboardButton(text="🗂 Yakunlangan testlar")],
        [KeyboardButton(text="👤 Profil")]
    ]
    # Check if user is an admin or owner
    if await is_admin(user_id):
        buttons.append([KeyboardButton(text="⚙️ Admin panel")])
        
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        placeholder="Bo'limni tanlang..."
    )

async def get_admin_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    # Check if super admin (owner)
    is_super = await is_owner(user_id)
    
    if is_super:
        buttons = [
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📝 Testlarni boshqarish")],
            [KeyboardButton(text="📢 Xabar yuborish"), KeyboardButton(text="🔗 Majburiy obunalar")],
            [KeyboardButton(text="🏷 Footer sozlamalari"), KeyboardButton(text="👮 Adminlarni boshqarish")],
            [KeyboardButton(text="📚 Janrlarni boshqarish"), KeyboardButton(text="🔙 Asosiy menyu")]
        ]
    else:
        # Standard admins: only Stats, Test Management, My Channels, and Genre Management
        buttons = [
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📝 Testlarni boshqarish")],
            [KeyboardButton(text="🔗 Mening kanallarim"), KeyboardButton(text="📚 Janrlarni boshqarish")],
            [KeyboardButton(text="🔙 Asosiy menyu")]
        ]
        
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        placeholder="Admin sozlamalari..."
    )

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    )
