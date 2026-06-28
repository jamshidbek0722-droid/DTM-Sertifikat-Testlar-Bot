from database.connection import db_conn
from database.models import UserModel
from typing import Optional

class UserRepo:
    @staticmethod
    async def get_user(user_id: int) -> Optional[UserModel]:
        doc = await db_conn.db.users.find_one({"user_id": user_id})
        return UserModel(**doc) if doc else None

    @staticmethod
    async def create_user(user_data: UserModel) -> UserModel:
        # Using upsert to avoid duplicate key errors on rapid start
        await db_conn.db.users.update_one(
            {"user_id": user_data.user_id},
            {"$set": user_data.model_dump()},
            upsert=True
        )
        return user_data

    @staticmethod
    async def increment_stats(user_id: int, score: int):
        await db_conn.db.users.update_one(
            {"user_id": user_id},
            {
                "$inc": {
                    "total_tests_taken": 1,
                    "total_score": score
                }
            }
        )
