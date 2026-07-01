from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_complete_profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Complete Profile", callback_data="complete_profile")]
        ]
    )

def get_gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🙋‍♂️ Male", callback_data="gender_Male"),
                InlineKeyboardButton(text="🙋‍♀️ Female", callback_data="gender_Female")
            ]
        ]
    )

def get_subscription_keyboard(channels: list, start_payload: str = "none") -> InlineKeyboardMarkup:
    buttons = []
    # Add each channel link
    for index, channel in enumerate(channels, start=1):
        invite_link = channel.get("invite_link", "https://t.me")
        title = channel.get("title", f"Channel {index}")
        buttons.append([InlineKeyboardButton(text=f"📢 Subscribe: {title}", url=invite_link)])
        
    # Check button contains start_payload so we don't lose FSM context
    buttons.append([InlineKeyboardButton(text="✅ Check Subscription", callback_data=f"check_sub:{start_payload}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_test_deep_link_keyboard(bot_username: str, test_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Check Answers", url=f"https://t.me/{bot_username}?start=test_{test_id}")]
        ]
    )

def get_admin_test_management_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Create Test", callback_data="admin_create_test"),
                InlineKeyboardButton(text="🗑 Delete Test", callback_data="admin_delete_test")
            ]
        ]
    )

def get_region_keyboard() -> InlineKeyboardMarkup:
    regions = [
        "Toshkent sh.", "Toshkent vil.",
        "Samarqand", "Buxoro",
        "Andijon", "Farg'ona",
        "Namangan", "Qashqadaryo",
        "Surxondaryo", "Xorazm",
        "Navoiy", "Jizzax",
        "Sirdaryo", "Qoraqalpog'iston"
    ]
    buttons = []
    for i in range(0, len(regions), 2):
        row = [
            InlineKeyboardButton(text=regions[i], callback_data=f"region:{regions[i]}")
        ]
        if i + 1 < len(regions):
            row.append(
                InlineKeyboardButton(text=regions[i+1], callback_data=f"region:{regions[i+1]}")
            )
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_subjects_keyboard(selected_subjects: list) -> InlineKeyboardMarkup:
    subjects = [
        "Matematika", "Fizika", "Kimyo", "Biologiya",
        "Ingliz tili", "Informatika", "Ona tili va adabiyot",
        "Tarix", "Geografiya", "Rus tili"
    ]
    buttons = []
    for i in range(0, len(subjects), 2):
        s1 = subjects[i]
        t1 = f"✅ {s1}" if s1 in selected_subjects else s1
        row = [
            InlineKeyboardButton(text=t1, callback_data=f"sub_toggle:{s1}")
        ]
        if i + 1 < len(subjects):
            s2 = subjects[i+1]
            t2 = f"✅ {s2}" if s2 in selected_subjects else s2
            row.append(
                InlineKeyboardButton(text=t2, callback_data=f"sub_toggle:{s2}")
            )
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="💾 Saqlash", callback_data="save_subjects")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
