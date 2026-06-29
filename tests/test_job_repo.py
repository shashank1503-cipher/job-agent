import pytest
from datetime import datetime
from sqlmodel import SQLModel, Session, create_engine

from api.models import Job, Run
from api.repositories.job_repo import list_jobs_grouped


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _run(session, started_at, **kwargs):
    run = Run(started_at=started_at, **kwargs)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _job(session, run_id, apply_url, **kwargs):
    job = Job(apply_url=apply_url, run_id=run_id, **kwargs)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def test_groups_jobs_by_run_newest_first(session):
    r1 = _run(session, datetime(2026, 6, 28))
    r2 = _run(session, datetime(2026, 6, 27))
    _job(session, r1.id, "https://a.com/1")
    _job(session, r2.id, "https://a.com/2")

    groups = list_jobs_grouped(session)

    assert len(groups) == 2
    assert groups[0][0].id == r1.id
    assert groups[1][0].id == r2.id


def test_jobs_within_group_ordered_by_score_desc(session):
    r = _run(session, datetime(2026, 6, 28))
    _job(session, r.id, "https://a.com/low", score=50)
    _job(session, r.id, "https://a.com/high", score=90)

    groups = list_jobs_grouped(session)
    jobs = groups[0][1]

    assert jobs[0].score == 90
    assert jobs[1].score == 50


def test_run_with_no_matching_jobs_still_included(session):
    r1 = _run(session, datetime(2026, 6, 28))
    r2 = _run(session, datetime(2026, 6, 27))
    _job(session, r1.id, "https://a.com/1", score=90)
    _job(session, r2.id, "https://a.com/2", score=30)

    groups = list_jobs_grouped(session, score_min=70)

    assert len(groups) == 2
    assert len(groups[0][1]) == 1
    assert len(groups[1][1]) == 0


def test_score_min_filter(session):
    r = _run(session, datetime(2026, 6, 28))
    _job(session, r.id, "https://a.com/low", score=30)
    _job(session, r.id, "https://a.com/high", score=80)

    groups = list_jobs_grouped(session, score_min=70)

    assert len(groups[0][1]) == 1
    assert groups[0][1][0].score == 80


def test_source_filter(session):
    r = _run(session, datetime(2026, 6, 28))
    _job(session, r.id, "https://a.com/1", source="lever")
    _job(session, r.id, "https://a.com/2", source="greenhouse")

    groups = list_jobs_grouped(session, source="lever")

    assert len(groups[0][1]) == 1
    assert groups[0][1][0].source == "lever"


def test_company_filter_case_insensitive(session):
    r = _run(session, datetime(2026, 6, 28))
    _job(session, r.id, "https://a.com/1", company="Stripe")
    _job(session, r.id, "https://a.com/2", company="Acme")

    groups = list_jobs_grouped(session, company="stripe")

    assert len(groups[0][1]) == 1
    assert groups[0][1][0].company == "Stripe"


def test_empty_db_returns_empty_list(session):
    assert list_jobs_grouped(session) == []
