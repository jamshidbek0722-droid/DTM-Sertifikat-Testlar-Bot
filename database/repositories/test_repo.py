from database.connection import db_conn
from database.models import TestModel, TestStatus
from typing import List, Optional

class TestRepo:
    @staticmethod
    async def create_test(test_data: TestModel) -> TestModel:
        await db_conn.db.tests.insert_one(test_data.model_dump())
        return test_data

    @staticmethod
    async def get_active_test(channel_id: int) -> Optional[TestModel]:
        doc = await db_conn.db.tests.find_one({
            "channel_id": channel_id,
            "status": TestStatus.active.value
        })
        return TestModel(**doc) if doc else None

    @staticmethod
    async def get_test_by_id(test_id: str) -> Optional[TestModel]:
        doc = await db_conn.db.tests.find_one({"test_id": test_id})
        return TestModel(**doc) if doc else None

    @staticmethod
    async def update_test_status(test_id: str, status: TestStatus) -> bool:
        result = await db_conn.db.tests.update_one(
            {"test_id": test_id},
            {"$set": {"status": status.value}}
        )
        return result.modified_count > 0

    @staticmethod
    async def get_tests_by_admin(admin_id: int, page: int, page_size: int = 10) -> List[TestModel]:
        skip = (page - 1) * page_size
        cursor = db_conn.db.tests.find({"admin_id": admin_id}).sort("created_at", -1).skip(skip).limit(page_size)
        return [TestModel(**doc) async for doc in cursor]

    @staticmethod
    async def delete_test(test_id: str) -> bool:
        result = await db_conn.db.tests.delete_one({"test_id": test_id})
        return result.deleted_count > 0
