from datetime import datetime

from sqlmodel import Session

from api.models import Run
from api.repositories import run_repo


def create_run(session: Session, filters_snapshot: str) -> Run:
    run = Run(started_at=datetime.utcnow(), filters_snapshot=filters_snapshot)
    return run_repo.save(session, run)


def finish_run(
    session: Session,
    run_id: int,
    jobs_fetched: int,
    jobs_qualified: int,
    jobs_rejected: int,
) -> Run:
    run = run_repo.get_by_id(session, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")
    run.finished_at = datetime.utcnow()
    run.jobs_fetched = jobs_fetched
    run.jobs_qualified = jobs_qualified
    run.jobs_rejected = jobs_rejected
    return run_repo.save(session, run)
