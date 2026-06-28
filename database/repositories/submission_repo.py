from database.connection import db_conn
from database.models import SubmissionModel
from typing import List, Optional

class SubmissionRepo:
    @staticmethod
    async def create_submission(submission_data: SubmissionModel) -> SubmissionModel:
        await db_conn.db.submissions.insert_one(submission_data.model_dump())
        return submission_data

    @staticmethod
    async def get_submission(test_id: str, user_id: int) -> Optional[SubmissionModel]:
        doc = await db_conn.db.submissions.find_one({
            "test_id": test_id,
            "user_id": user_id
        })
        return SubmissionModel(**doc) if doc else None

    @staticmethod
    async def get_leaderboard(test_id: str, limit: int = 10) -> List[SubmissionModel]:
        # Sort by score desc, then by submitted_at asc (tiebreaker)
        cursor = db_conn.db.submissions.find({
            "test_id": test_id,
            "is_late": False
        }).sort([("score", -1), ("submitted_at", 1)]).limit(limit)
        return [SubmissionModel(**doc) async for doc in cursor]
