import logging
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config import config

logger = logging.getLogger(__name__)

class DatabaseConnection:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    async def connect(cls):
        retries = 3
        backoff = 2
        for attempt in range(1, retries + 1):
            try:
                logger.info(f"Connecting to MongoDB (Attempt {attempt}/{retries})...")
                cls.client = AsyncIOMotorClient(
                    config.mongodb_uri,
                    minPoolSize=5,
                    maxPoolSize=20,
                    serverSelectionTimeoutMS=5000
                )
                # Ping health check
                await cls.client.admin.command('ping')
                
                # Get the database (using explicit name 'mock_test_db' since URI might not have a default)
                cls.db = cls.client.get_database('mock_test_db')
                logger.info(f"MongoDB connected successfully. Database: {cls.db.name}")
                
                await cls.create_indexes()
                return
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                if attempt < retries:
                    logger.info(f"Retrying in {backoff} seconds...")
                    await asyncio.sleep(backoff)
                else:
                    logger.error("Max retries reached. Could not connect to database.")
                    raise e

    @classmethod
    async def disconnect(cls):
        if cls.client:
            logger.info("Closing MongoDB connection...")
            cls.client.close()
            logger.info("MongoDB connection closed.")

    @classmethod
    async def create_indexes(cls):
        try:
            # submissions: (test_id, user_id) unique
            await cls.db.submissions.create_index(
                [("test_id", 1), ("user_id", 1)],
                unique=True
            )
            # tests: (channel_id, status)
            await cls.db.tests.create_index(
                [("channel_id", 1), ("status", 1)]
            )
            # channels: (admin_id, channel_id)
            await cls.db.channels.create_index(
                [("admin_id", 1), ("channel_id", 1)]
            )
            logger.info("Database indexes ensured.")
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")

db_conn = DatabaseConnection()
