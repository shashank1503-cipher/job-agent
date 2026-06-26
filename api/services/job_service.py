import json
from datetime import datetime
from typing import Optional

from sqlmodel import Session

from api.models import Job
from api.repositories import job_repo


def _parse_date(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def upsert_job(session: Session, job_data: dict, run_id: int) -> Job:
    apply_url = job_data.get("apply_url") or job_data.get("url", "")
    if not apply_url:
        return None

    analysis = job_data.get("match_analysis", {})
    score = analysis.get("score", 0)
    keyword_score = analysis.get("keyword_score", 0)
    analysis_json = json.dumps(analysis, default=str) if analysis else None

    existing = job_repo.get_by_apply_url(session, apply_url)
    if existing:
        existing.description = job_data.get("description") or existing.description
        existing.score = score
        existing.keyword_score = keyword_score
        existing.date_scraped = datetime.utcnow()
        existing.run_id = run_id
        existing.analysis_json = analysis_json
        return job_repo.upsert(session, existing)

    job = Job(
        title=job_data.get("title", ""),
        company=job_data.get("company", ""),
        location=job_data.get("location", ""),
        description=job_data.get("description", ""),
        salary=job_data.get("salary", ""),
        score=score,
        keyword_score=keyword_score,
        source=job_data.get("source", ""),
        apply_url=apply_url,
        url=job_data.get("url", ""),
        date_posted=_parse_date(str(job_data.get("date_posted", "") or "")),
        run_id=run_id,
        analysis_json=analysis_json,
    )
    return job_repo.upsert(session, job)
