from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from api.database import get_session
from api.repositories import run_repo

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("")
def list_runs(session: Session = Depends(get_session)):
    return run_repo.list_runs(session)


@router.get("/{run_id}/summary")
def get_run_summary(run_id: int, session: Session = Depends(get_session)):
    run = run_repo.get_by_id(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": run.id,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "jobs_fetched": run.jobs_fetched,
        "jobs_qualified": run.jobs_qualified,
        "jobs_rejected": run.jobs_rejected,
    }
