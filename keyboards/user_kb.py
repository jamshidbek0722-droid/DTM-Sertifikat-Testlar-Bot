from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_join_test_kb(test_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Ishtirok etish", callback_data=f"join_test_{test_id}")]
    ])
