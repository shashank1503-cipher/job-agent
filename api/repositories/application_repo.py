from typing import Optional

from sqlmodel import Session, select

from api.models import Application, Job


def get_by_id(session: Session, app_id: int) -> Optional[Application]:
    return session.get(Application, app_id)


def get_by_job_id(session: Session, job_id: int) -> Optional[Application]:
    return session.exec(select(Application).where(Application.job_id == job_id)).first()


def list_applications(session: Session) -> list[dict]:
    rows = session.exec(
        select(Application, Job)
        .where(Application.job_id == Job.id)
        .order_by(Application.applied_at.desc())
    ).all()
    result = []
    for app, job in rows:
        result.append(
            {
                "id": app.id,
                "job_id": app.job_id,
                "status": app.status,
                "applied_at": app.applied_at,
                "notes": app.notes,
                "resume_used": app.resume_used,
                "title": job.title,
                "company": job.company,
                "apply_url": job.apply_url,
            }
        )
    return result


def save(session: Session, app: Application) -> Application:
    session.add(app)
    session.commit()
    session.refresh(app)
    return app
