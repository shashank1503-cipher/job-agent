import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from api.database import get_session
from api.repositories import job_repo

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs(
    score_min: int = 0,
    source: Optional[str] = None,
    company: Optional[str] = None,
    session: Session = Depends(get_session),
):
    groups = job_repo.list_jobs_grouped(
        session, score_min=score_min, source=source, company=company
    )
    return [
        {
            "run": {
                "id": run.id,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "jobs_fetched": run.jobs_fetched,
                "jobs_qualified": run.jobs_qualified,
                "jobs_rejected": run.jobs_rejected,
            },
            "jobs": [
                {
                    "id": j.id,
                    "title": j.title,
                    "company": j.company,
                    "location": j.location,
                    "salary": j.salary,
                    "score": j.score,
                    "keyword_score": j.keyword_score,
                    "source": j.source,
                    "apply_url": j.apply_url,
                    "url": j.url,
                    "date_posted": j.date_posted,
                    "date_scraped": j.date_scraped,
                    "run_id": j.run_id,
                }
                for j in jobs
            ],
        }
        for run, jobs in groups
    ]


@router.get("/{job_id}")
def get_job(job_id: int, session: Session = Depends(get_session)):
    job = job_repo.get_by_id(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    analysis = json.loads(job.analysis_json) if job.analysis_json else {}
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description": job.description,
        "salary": job.salary,
        "score": job.score,
        "keyword_score": job.keyword_score,
        "source": job.source,
        "apply_url": job.apply_url,
        "url": job.url,
        "date_posted": job.date_posted,
        "date_scraped": job.date_scraped,
        "run_id": job.run_id,
        "score_breakdown": analysis,
    }
