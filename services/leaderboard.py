from database.repositories.submission_repo import SubmissionRepo
from database.repositories.test_repo import TestRepo
from database.connection import db_conn
from utils.formatters import fmt

async def generate_leaderboard_text(test_id: str) -> str:
    test = await TestRepo.get_test_by_id(test_id)
    if not test:
        return ""
        
    submissions = await SubmissionRepo.get_leaderboard(test_id, limit=10)
    
    # Calculate stats
    all_subs = await db_conn.db.submissions.find({"test_id": test_id, "is_late": False}).to_list(length=None)
    total_participants = len(all_subs)
    
    if total_participants == 0:
        avg_score = 0
        max_score = 0
    else:
        avg_score = sum(s["score"] for s in all_subs) / total_participants
        max_score = max(s["score"] for s in all_subs)
        
    return fmt.format_leaderboard(
        title=test.title,
        total_participants=total_participants,
        top_submissions=submissions,
        avg_score=avg_score,
        max_score=max_score,
        total_questions=test.total_questions,
        cta_link="https://t.me/YourBot"
    )
