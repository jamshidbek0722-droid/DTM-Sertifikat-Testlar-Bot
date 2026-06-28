from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from pymongo import MongoClient
from config import config
from services.notifier import post_test_to_channel, post_leaderboard_to_channel, post_solution_to_channel
import logging

logger = logging.getLogger(__name__)
mongo_client = MongoClient(config.mongodb_uri)

jobstores = {
    'default': MongoDBJobStore(database='mock_test_db', collection='apscheduler_jobs', client=mongo_client)
}
scheduler = AsyncIOScheduler(jobstores=jobstores)

def schedule_test_post(test_id: str, channel_id: int, post_time):
    scheduler.add_job(post_test_to_channel, 'date', run_date=post_time, args=[test_id, channel_id])
    logger.info(f"Scheduled test post for {test_id} at {post_time}")

def schedule_test_close(test_id: str, close_time, channel_id: int):
    scheduler.add_job(post_leaderboard_to_channel, 'date', run_date=close_time, args=[test_id, channel_id])
    logger.info(f"Scheduled test close and leaderboard for {test_id} at {close_time}")

def schedule_solution_post(test_id: str, channel_id: int, solution_time):
    scheduler.add_job(post_solution_to_channel, 'date', run_date=solution_time, args=[test_id, channel_id])
    logger.info(f"Scheduled solution post for {test_id} at {solution_time}")

def start_scheduler():
    scheduler.start()
    logger.info("APScheduler started.")
