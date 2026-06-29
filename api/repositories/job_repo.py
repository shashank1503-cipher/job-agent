from typing import Optional

from sqlmodel import Session, select

from api.models import Job, Run


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


def list_jobs_grouped(
    session: Session,
    score_min: int = 0,
    source: Optional[str] = None,
    company: Optional[str] = None,
) -> list[tuple[Run, list[Job]]]:
    runs = list(session.exec(select(Run).order_by(Run.started_at.desc())).all())

    q = select(Job)
    if score_min:
        q = q.where(Job.score >= score_min)
    if source:
        q = q.where(Job.source == source)
    if company:
        q = q.where(Job.company.ilike(f"%{company}%"))
    q = q.order_by(Job.score.desc())
    all_jobs = list(session.exec(q).all())

    jobs_by_run: dict[int, list[Job]] = {}
    for job in all_jobs:
        jobs_by_run.setdefault(job.run_id, []).append(job)

    return [(run, jobs_by_run.get(run.id, [])) for run in runs]


def upsert(session: Session, job: Job) -> Job:
    session.add(job)
    session.commit()
    session.refresh(job)
    return job
