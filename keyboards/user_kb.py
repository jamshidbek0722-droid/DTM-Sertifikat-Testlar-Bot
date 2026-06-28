from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def get_join_test_kb(test_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Ishtirok etish", callback_data=f"join_test_{test_id}")]
    ])

def get_main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Test ishlash")],
            [KeyboardButton(text="📊 Mening natijalarim"), KeyboardButton(text="ℹ️ Qoidalar")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Quyidagilardan birini tanlang..."
    )
