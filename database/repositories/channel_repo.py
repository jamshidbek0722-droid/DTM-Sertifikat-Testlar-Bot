from database.connection import db_conn
from database.models import ChannelModel
from typing import List, Optional

class ChannelRepo:
    @staticmethod
    async def add_channel(channel_data: ChannelModel) -> ChannelModel:
        await db_conn.db.channels.update_one(
            {"channel_id": channel_data.channel_id},
            {"$set": channel_data.model_dump()},
            upsert=True
        )
        return channel_data

    @staticmethod
    async def get_channels_by_admin(admin_id: int) -> List[ChannelModel]:
        cursor = db_conn.db.channels.find({"admin_id": admin_id, "is_active": True})
        return [ChannelModel(**doc) async for doc in cursor]

    @staticmethod
    async def get_channel(channel_id: int) -> Optional[ChannelModel]:
        doc = await db_conn.db.channels.find_one({"channel_id": channel_id})
        return ChannelModel(**doc) if doc else None
