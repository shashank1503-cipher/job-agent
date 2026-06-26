from typing import Optional

from sqlmodel import Session, select

from api.models import Job


def get_by_apply_url(session: Session, apply_url: str) -> Optional[Job]:
    return session.exec(select(Job).where(Job.apply_url == apply_url)).first()


def get_by_id(session: Session, job_id: int) -> Optional[Job]:
    return session.get(Job, job_id)


def list_jobs(
    session: Session,
    score_min: int = 0,
    source: Optional[str] = None,
    company: Optional[str] = None,
) -> list[Job]:
    q = select(Job)
    if score_min:
        q = q.where(Job.score >= score_min)
    if source:
        q = q.where(Job.source == source)
    if company:
        q = q.where(Job.company.ilike(f"%{company}%"))
    q = q.order_by(Job.score.desc())
    return list(session.exec(q).all())


def upsert(session: Session, job: Job) -> Job:
    session.add(job)
    session.commit()
    session.refresh(job)
    return job
