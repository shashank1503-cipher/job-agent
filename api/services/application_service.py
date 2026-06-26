from datetime import datetime

from fastapi import HTTPException
from sqlmodel import Session

from api.models import Application
from api.repositories import application_repo

_VALID_TRANSITIONS: dict[str, list[str]] = {
    "applied": ["interviewing", "rejected"],
    "interviewing": ["offered", "rejected"],
    "offered": [],
    "rejected": [],
}


def create_application(session: Session, job_id: int) -> Application:
    if application_repo.get_by_job_id(session, job_id):
        raise HTTPException(
            status_code=409, detail="Application already exists for this job"
        )
    app = Application(job_id=job_id, status="applied", applied_at=datetime.utcnow())
    return application_repo.save(session, app)


def update_status(session: Session, app_id: int, new_status: str) -> Application:
    app = application_repo.get_by_id(session, app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")

    allowed = _VALID_TRANSITIONS.get(app.status, [])
    if not allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Status '{app.status}' is terminal — no further transitions allowed",
        )
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {app.status} → {new_status}. Allowed: {allowed}",
        )

    app.status = new_status
    return application_repo.save(session, app)


def update_notes(session: Session, app_id: int, notes: str) -> Application:
    app = application_repo.get_by_id(session, app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    app.notes = notes
    return application_repo.save(session, app)
