from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


class Run(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    started_at: datetime
    finished_at: Optional[datetime] = None
    jobs_fetched: int = 0
    jobs_qualified: int = 0
    jobs_rejected: int = 0
    filters_snapshot: str = ""


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    salary: str = ""
    score: int = 0
    keyword_score: int = 0
    source: str = ""
    apply_url: str = Field(sa_column=Column(String, unique=True, index=True))
    url: str = ""
    date_posted: Optional[datetime] = None
    date_scraped: datetime = Field(default_factory=datetime.utcnow)
    run_id: int
    analysis_json: Optional[str] = (
        None  # JSON of full match_analysis for score breakdown
    )


class Application(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", unique=True)
    status: str = "applied"  # applied | interviewing | offered | rejected
    applied_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
    resume_used: Optional[str] = None
