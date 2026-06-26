from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from api.database import get_session
from api.repositories import application_repo
from api.services import application_service

router = APIRouter(prefix="/applications", tags=["applications"])


class CreateApplicationBody(BaseModel):
    job_id: int


class UpdateApplicationBody(BaseModel):
    status: str = None
    notes: str = None


@router.get("")
def list_applications(session: Session = Depends(get_session)):
    return application_repo.list_applications(session)


@router.post("", status_code=201)
def create_application(
    body: CreateApplicationBody, session: Session = Depends(get_session)
):
    return application_service.create_application(session, body.job_id)


@router.patch("/{app_id}")
def update_application(
    app_id: int, body: UpdateApplicationBody, session: Session = Depends(get_session)
):
    app = None
    if body.status is not None:
        app = application_service.update_status(session, app_id, body.status)
    if body.notes is not None:
        app = application_service.update_notes(session, app_id, body.notes)
    if app is None:
        from api.repositories.application_repo import get_by_id
        from fastapi import HTTPException

        app = get_by_id(session, app_id)
        if app is None:
            raise HTTPException(status_code=404, detail="Application not found")
    return app
