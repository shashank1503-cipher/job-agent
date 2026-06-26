from typing import Optional

from sqlmodel import Session, select

from api.models import Run


def get_by_id(session: Session, run_id: int) -> Optional[Run]:
    return session.get(Run, run_id)


def list_runs(session: Session) -> list[Run]:
    return list(session.exec(select(Run).order_by(Run.started_at.desc())).all())


def save(session: Session, run: Run) -> Run:
    session.add(run)
    session.commit()
    session.refresh(run)
    return run
