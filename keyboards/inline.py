import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_complete_profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Profilni to'ldirish", callback_data="complete_profile")]
        ]
    )

def get_gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🙋‍♂️ Erkak", callback_data="gender_Male"),
                InlineKeyboardButton(text="🙋‍♀️ Ayol", callback_data="gender_Female")
            ]
        ]
    )

def get_subscription_keyboard(channels: list, start_payload: str = "none") -> InlineKeyboardMarkup:
    buttons = []
    # Add each channel link
    for index, channel in enumerate(channels, start=1):
        invite_link = channel.get("invite_link", "https://t.me")
        title = channel.get("title", f"Kanal {index}")
        buttons.append([InlineKeyboardButton(text=f"📢 A'zo bo'lish: {title}", url=invite_link)])
        
    # Check button contains start_payload so we don't lose FSM context
    buttons.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data=f"check_sub:{start_payload}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_test_deep_link_keyboard(bot_username: str, test_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Javoblarni tekshirish", url=f"https://t.me/{bot_username}?start=test_{test_id}")]
        ]
    )

def get_admin_test_management_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Test yaratish", callback_data="admin_create_test"),
                InlineKeyboardButton(text="🗑 Testni o'chirish", callback_data="admin_delete_test")
            ]
        ]
    )

def get_region_keyboard() -> InlineKeyboardMarkup:
    regions = [
        "Toshkent shahri", "Toshkent viloyati",
        "Samarqand viloyati", "Buxoro viloyati",
        "Andijon viloyati", "Farg'ona viloyati",
        "Namangan viloyati", "Qashqadaryo viloyati",
        "Surxondaryo viloyati", "Xorazm viloyati",
        "Navoiy viloyati", "Jizzax viloyati",
        "Sirdaryo viloyati", "Qoraqalpog'iston Res."
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
        "Tarix", "Geografiya"
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
    buttons.append([InlineKeyboardButton(text="📥 Saqlash", callback_data="save_subjects")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Genre and Completed Test Management Keyboards ---

def get_genre_selection_keyboard(genres: list) -> InlineKeyboardMarkup:
    buttons = []
    for g in genres:
        buttons.append([InlineKeyboardButton(text=g["name"], callback_data=f"create_test_genre:{g['genre_id']}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_past_genres_keyboard(genres: list) -> InlineKeyboardMarkup:
    buttons = []
    for g in genres:
        buttons.append([InlineKeyboardButton(text=g["name"], callback_data=f"past_genre:{g['genre_id']}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_past_tests_keyboard(tests: list) -> InlineKeyboardMarkup:
    buttons = []
    for t in tests:
        # local time representation (UTC+5)
        local_time = t.get("start_time") + datetime.timedelta(hours=5) if t.get("start_time") else datetime.datetime.now()
        date_str = local_time.strftime("%d.%m %H:%M")
        name = t.get("test_name", "Nomsiz test")
        btn_text = f"📝 {name} ({date_str})"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"view_past_test:{t['test_id']}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_mandatory_channels_manage_keyboard(channels: list) -> InlineKeyboardMarkup:
    buttons = []
    for ch in channels:
        status_emoji = "✅" if ch.get("is_active", True) else "❌"
        buttons.append([
            InlineKeyboardButton(text=f"{ch['title']}", url=ch.get("invite_link", "https://t.me")),
            InlineKeyboardButton(text=f"Holat: {status_emoji}", callback_data=f"toggle_mchan:{ch['channel_id']}"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_mchan:{ch['channel_id']}")
        ])
    buttons.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_mchan")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_test_channels_manage_keyboard(channels: list) -> InlineKeyboardMarkup:
    buttons = []
    for ch in channels:
        buttons.append([
            InlineKeyboardButton(text=f"{ch['title']}", url=ch.get("invite_link", "https://t.me")),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_tchan:{ch['channel_id']}")
        ])
    buttons.append([InlineKeyboardButton(text="➕ Yangi kanal qo'shish", callback_data="add_tchan")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_genres_manage_keyboard(genres: list) -> InlineKeyboardMarkup:
    buttons = []
    for g in genres:
        buttons.append([
            InlineKeyboardButton(text=g["name"], callback_data="noop"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_genre:{g['genre_id']}")
        ])
    buttons.append([InlineKeyboardButton(text="➕ Yangi janr qo'shish", callback_data="add_genre")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
