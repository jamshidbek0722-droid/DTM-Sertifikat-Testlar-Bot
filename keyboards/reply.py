from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from database.db import is_admin, is_owner

async def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📝 Active Tests"), KeyboardButton(text="🗂 Past Tests")],
        [KeyboardButton(text="👤 Profile")]
    ]
    # Check if user is an admin or owner
    if await is_admin(user_id):
        buttons.append([KeyboardButton(text="⚙️ Admin Panel")])
        
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        placeholder="Select an option..."
    )

async def get_admin_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    # Check if super admin (owner)
    is_super = await is_owner(user_id)
    
    if is_super:
        buttons = [
            [KeyboardButton(text="📊 Statistics"), KeyboardButton(text="📝 Test Management")],
            [KeyboardButton(text="📢 Broadcast"), KeyboardButton(text="🔗 Mandatory Subs")],
            [KeyboardButton(text="🏷 Footer Settings"), KeyboardButton(text="👮 Add/Remove Admins")],
            [KeyboardButton(text="🔙 Main Menu")]
        ]
    else:
        # Standard admins: only Stats, Test Management, and My Channels
        buttons = [
            [KeyboardButton(text="📊 Statistics"), KeyboardButton(text="📝 Test Management")],
            [KeyboardButton(text="🔗 My Channels"), KeyboardButton(text="🔙 Main Menu")]
        ]
        
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        placeholder="Admin options..."
    )

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Cancel")]],
        resize_keyboard=True
    )
