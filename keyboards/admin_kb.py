from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.models import ChannelModel

def get_admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Test yuklash", callback_data="admin_upload_test")],
        [InlineKeyboardButton(text="📋 Mening testlarim", callback_data="admin_my_tests")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Kanallarni boshqarish", callback_data="admin_manage_channels")]
    ])

def get_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_cancel")]
    ])

def get_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="admin_confirm_upload")],
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_cancel")]
    ])

def get_skip_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏩ O'tkazib yuborish", callback_data="admin_skip")],
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_cancel")]
    ])

def get_channels_kb(channels: list[ChannelModel]) -> InlineKeyboardMarkup:
    kb = []
    for ch in channels:
        kb.append([InlineKeyboardButton(text=ch.channel_username or str(ch.channel_id), callback_data=f"sel_chan_{ch.channel_id}")])
    kb.append([InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)
