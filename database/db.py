import datetime
import uuid
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, OWNER_ID

client = AsyncIOMotorClient(MONGO_URI)
db = client['dtm_test_bot']

# Collections
users_col = db['users']
admins_col = db['admins']
mandatory_channels_col = db['mandatory_channels']
test_channels_col = db['test_channels']
tests_col = db['tests']
submissions_col = db['submissions']
settings_col = db['settings']
genres_col = db['genres']

async def init_db():
    """Initialize database indexes"""
    await users_col.create_index("tg_id", unique=True)
    await tests_col.create_index("test_id", unique=True)
    await mandatory_channels_col.create_index("channel_id", unique=True)
    await test_channels_col.create_index("channel_id", unique=True)
    await genres_col.create_index("genre_id", unique=True)
    await submissions_col.create_index([("user_id", 1), ("test_id", 1)], unique=True)

# --- Admin Helpers ---
async def is_owner(tg_id: int) -> bool:
    return tg_id == OWNER_ID

async def is_admin(tg_id: int) -> bool:
    if tg_id == OWNER_ID:
        return True
    admin = await admins_col.find_one({"tg_id": tg_id})
    return admin is not None

async def add_admin(tg_id: int, added_by: int) -> bool:
    if await admins_col.find_one({"tg_id": tg_id}):
        return False
    await admins_col.insert_one({
        "tg_id": tg_id,
        "added_by": added_by,
        "role": "standard",
        "added_at": datetime.datetime.utcnow()
    })
    return True

async def remove_admin(tg_id: int) -> bool:
    res = await admins_col.delete_one({"tg_id": tg_id})
    return res.deleted_count > 0

async def get_all_admins() -> list:
    admins = []
    async for admin in admins_col.find({}):
        admins.append(admin)
    return admins

# --- User Helpers ---
async def get_user(tg_id: int) -> dict:
    return await users_col.find_one({"tg_id": tg_id})

async def create_user(tg_id: int, name: str, username: str = None, referred_by: int = None) -> dict:
    user = await get_user(tg_id)
    if not user:
        new_user = {
            "tg_id": tg_id,
            "name": name,
            "username": username,
            "registered": False,
            "region": None,
            "gender": None,
            "age": None,
            "subject": None,
            "referred_by": referred_by,
            "referrals_count": 0,
            "created_at": datetime.datetime.utcnow()
        }
        await users_col.insert_one(new_user)
        if referred_by:
            # Increment referrals count for the inviter
            await users_col.update_one({"tg_id": referred_by}, {"$inc": {"referrals_count": 1}})
        return new_user
    return user

async def register_user(tg_id: int, region: str, gender: str, age: int, subject: str) -> bool:
    res = await users_col.update_one(
        {"tg_id": tg_id},
        {"$set": {
            "region": region,
            "gender": gender,
            "age": age,
            "subject": subject,
            "registered": True
        }}
    )
    return res.modified_count > 0

async def get_total_users_count() -> int:
    return await users_col.count_documents({})

async def get_registered_users_count() -> int:
    return await users_col.count_documents({"registered": True})

async def get_users_breakdown() -> dict:
    """Gets breakdown of users by region and gender"""
    pipeline = [
        {"$match": {"registered": True}},
        {"$group": {
            "_id": {
                "region": "$region",
                "gender": "$gender"
            },
            "count": {"$sum": 1}
        }}
    ]
    cursor = users_col.aggregate(pipeline)
    breakdown = {}
    async for doc in cursor:
        region = doc["_id"].get("region", "Unknown")
        gender = doc["_id"].get("gender", "Unknown")
        count = doc["count"]
        if region not in breakdown:
            breakdown[region] = {"Male": 0, "Female": 0, "Total": 0}
        breakdown[region][gender] = breakdown[region].get(gender, 0) + count
        breakdown[region]["Total"] += count
    return breakdown

# --- Mandatory Channel Helpers (For Forced Subscription) ---
async def add_mandatory_channel(channel_id: int, invite_link: str, title: str, added_by: int) -> bool:
    try:
        await mandatory_channels_col.update_one(
            {"channel_id": channel_id},
            {"$set": {
                "invite_link": invite_link,
                "title": title,
                "added_by": added_by,
                "is_active": True
            }},
            upsert=True
        )
        return True
    except Exception:
        return False

async def remove_mandatory_channel(channel_id: int) -> bool:
    res = await mandatory_channels_col.delete_one({"channel_id": channel_id})
    return res.deleted_count > 0

async def get_all_mandatory_channels() -> list:
    channels = []
    async for channel in mandatory_channels_col.find({}):
        channels.append(channel)
    return channels

async def get_active_mandatory_channels() -> list:
    channels = []
    async for channel in mandatory_channels_col.find({"is_active": {"$ne": False}}):
        channels.append(channel)
    return channels

async def toggle_mandatory_channel_status(channel_id: int) -> bool:
    channel = await mandatory_channels_col.find_one({"channel_id": channel_id})
    if not channel:
        return False
    new_status = not channel.get("is_active", True)
    await mandatory_channels_col.update_one({"channel_id": channel_id}, {"$set": {"is_active": new_status}})
    return True

async def get_mandatory_channel(channel_id: int) -> dict:
    return await mandatory_channels_col.find_one({"channel_id": channel_id})

# Backward compatibility map
async def get_all_channels() -> list:
    return await get_active_mandatory_channels()

# --- Test Channel Helpers ---
async def add_test_channel(channel_id: int, invite_link: str, title: str, added_by: int) -> bool:
    try:
        await test_channels_col.update_one(
            {"channel_id": channel_id},
            {"$set": {
                "invite_link": invite_link,
                "title": title,
                "added_by": added_by
            }},
            upsert=True
        )
        return True
    except Exception:
        return False

async def remove_test_channel(channel_id: int) -> bool:
    res = await test_channels_col.delete_one({"channel_id": channel_id})
    return res.deleted_count > 0

async def get_all_test_channels() -> list:
    channels = []
    async for channel in test_channels_col.find({}):
        channels.append(channel)
    return channels

async def get_test_channels_by_admin(admin_id: int) -> list:
    if admin_id == OWNER_ID:
        return await get_all_test_channels()
    channels = []
    async for channel in test_channels_col.find({"added_by": admin_id}):
        channels.append(channel)
    return channels

async def get_test_channel(channel_id: int) -> dict:
    return await test_channels_col.find_one({"channel_id": channel_id})

async def get_channels_by_admin(admin_id: int) -> list:
    return await get_test_channels_by_admin(admin_id)

# --- Global Footer Settings ---
async def get_global_footer() -> str:
    setting = await settings_col.find_one({"key": "global_footer"})
    return setting["value"] if setting else ""

async def set_global_footer(text: str):
    await settings_col.update_one(
        {"key": "global_footer"},
        {"$set": {"value": text}},
        upsert=True
    )

# --- Genre Helpers ---
async def add_genre(name: str, added_by: int) -> bool:
    genre_id = str(uuid.uuid4())[:8]
    try:
        await genres_col.insert_one({
            "genre_id": genre_id,
            "name": name,
            "added_by": added_by,
            "created_at": datetime.datetime.utcnow()
        })
        return True
    except Exception:
        return False

async def delete_genre(genre_id: str) -> bool:
    res = await genres_col.delete_one({"genre_id": genre_id})
    return res.deleted_count > 0

async def get_all_genres() -> list:
    genres = []
    async for genre in genres_col.find({}):
        genres.append(genre)
    return genres

async def get_genre(genre_id: str) -> dict:
    return await genres_col.find_one({"genre_id": genre_id})

# --- Test Helpers ---
async def create_test(test_id: str, creator_id: int, file_ids: list, answer_key: str, 
                      solutions_text: str, channel_id: int, start_time: datetime.datetime, 
                      duration_minutes: int, test_name: str, genre_id: str, solutions_media: dict = None) -> bool:
    try:
        await tests_col.insert_one({
            "test_id": test_id,
            "creator_id": creator_id,
            "file_ids": file_ids,
            "answer_key": answer_key.lower(),
            "solutions_text": solutions_text,
            "solutions_media": solutions_media,
            "channel_id": channel_id,
            "start_time": start_time,
            "duration_minutes": duration_minutes,
            "status": "scheduled",  # scheduled, active, finished
            "test_post_msg_id": None,
            "created_at": datetime.datetime.utcnow(),
            "test_name": test_name,
            "genre_id": genre_id
        })
        return True
    except Exception:
        return False

async def get_test(test_id: str) -> dict:
    return await tests_col.find_one({"test_id": test_id})

async def get_active_tests() -> list:
    tests = []
    async for test in tests_col.find({"status": "active"}):
        tests.append(test)
    return tests

async def get_past_tests() -> list:
    tests = []
    async for test in tests_col.find({"status": "finished"}):
        tests.append(test)
    return tests

async def get_tests_by_creator(creator_id: int) -> list:
    tests = []
    async for test in tests_col.find({"creator_id": creator_id}):
        tests.append(test)
    return tests

async def update_test_status(test_id: str, status: str) -> bool:
    res = await tests_col.update_one({"test_id": test_id}, {"$set": {"status": status}})
    return res.modified_count > 0

async def update_test_post_msg_id(test_id: str, message_id: int) -> bool:
    res = await tests_col.update_one({"test_id": test_id}, {"$set": {"test_post_msg_id": message_id}})
    return res.modified_count > 0

async def delete_test(test_id: str) -> bool:
    res = await tests_col.delete_one({"test_id": test_id})
    return res.deleted_count > 0

async def get_total_tests_count() -> int:
    return await tests_col.count_documents({})

# --- Submission Helpers ---
async def create_submission(user_id: int, test_id: str, answers: str, score: float, 
                            correct_count: int, total_count: int, time_taken_seconds: int) -> bool:
    try:
        await submissions_col.update_one(
            {"user_id": user_id, "test_id": test_id},
            {"$set": {
                "answers": answers.lower(),
                "score": score,
                "correct_count": correct_count,
                "total_count": total_count,
                "time_taken_seconds": time_taken_seconds,
                "submitted_at": datetime.datetime.utcnow()
            }},
            upsert=True
        )
        return True
    except Exception:
        return False

async def get_submission(user_id: int, test_id: str) -> dict:
    return await submissions_col.find_one({"user_id": user_id, "test_id": test_id})

async def get_submissions_for_test(test_id: str) -> list:
    submissions = []
    async for sub in submissions_col.find({"test_id": test_id}).sort([("score", -1), ("time_taken_seconds", 1)]):
        submissions.append(sub)
    return submissions

async def get_total_submissions_count() -> int:
    return await submissions_col.count_documents({})
