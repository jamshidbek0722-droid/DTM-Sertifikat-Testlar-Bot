from typing import Any, Dict, Optional
from aiogram.fsm.storage.base import BaseStorage, StorageKey, StateType
from aiogram.fsm.state import State
import logging

logger = logging.getLogger(__name__)

class MongoStorage(BaseStorage):
    def __init__(self, db_conn):
        self.db_conn = db_conn

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        try:
            state_val = state.state if isinstance(state, State) else state
            await self.db_conn.db.fsm_states.update_one(
                {"chat_id": key.chat_id, "user_id": key.user_id},
                {"$set": {"state": state_val}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"MongoStorage set_state error: {e}")

    async def get_state(self, key: StorageKey) -> Optional[str]:
        try:
            doc = await self.db_conn.db.fsm_states.find_one({"chat_id": key.chat_id, "user_id": key.user_id})
            return doc.get("state") if doc else None
        except Exception as e:
            logger.error(f"MongoStorage get_state error: {e}")
            return None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        try:
            await self.db_conn.db.fsm_data.update_one(
                {"chat_id": key.chat_id, "user_id": key.user_id},
                {"$set": {"data": data}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"MongoStorage set_data error: {e}")

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        try:
            doc = await self.db_conn.db.fsm_data.find_one({"chat_id": key.chat_id, "user_id": key.user_id})
            return doc.get("data", {}) if doc else {}
        except Exception as e:
            logger.error(f"MongoStorage get_data error: {e}")
            return {}

    async def close(self) -> None:
        pass
