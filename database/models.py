from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum

def get_utc_now():
    return datetime.now(timezone.utc)

class TestStatus(str, Enum):
    scheduled = "scheduled"
    active = "active"
    grading = "grading"
    completed = "completed"

class TestModel(BaseModel):
    test_id: str
    title: str
    subject: str
    channel_id: int
    admin_id: int
    pdf_file_id: str
    answer_key: Dict[str, str]
    solution_file_id: Optional[str] = None
    total_questions: int
    duration: int = 60
    status: TestStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    scheduled_post_time: Optional[datetime] = None
    result_post_time: Optional[datetime] = None
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

class SubmissionModel(BaseModel):
    submission_id: str
    test_id: str
    user_id: int
    username: Optional[str] = None
    full_name: str
    raw_answer_string: str
    parsed_answers: Dict[str, str]
    score: int
    percentage: float
    submitted_at: datetime = Field(default_factory=get_utc_now)
    is_late: bool

class ChannelModel(BaseModel):
    channel_id: int
    channel_username: Optional[str] = None
    subject: str
    admin_id: int
    is_active: bool = True

class AdminModel(BaseModel):
    user_id: int
    username: Optional[str] = None
    assigned_channel_ids: List[int] = Field(default_factory=list)
    added_by: int
    added_at: datetime = Field(default_factory=get_utc_now)

class UserModel(BaseModel):
    user_id: int
    username: Optional[str] = None
    full_name: str
    joined_at: datetime = Field(default_factory=get_utc_now)
    total_tests_taken: int = 0
    total_score: int = 0
