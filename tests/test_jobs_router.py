from datetime import datetime
from sqlmodel import Session

from api.models import Job, Run


# conftest.py provides the client and test_engine fixtures


def _seed(test_engine):
    with Session(test_engine) as s:
        r1 = Run(started_at=datetime(2026, 6, 28), jobs_fetched=2, jobs_qualified=2)
        r2 = Run(started_at=datetime(2026, 6, 27), jobs_fetched=1, jobs_qualified=1)
        s.add(r1)
        s.add(r2)
        s.commit()
        s.refresh(r1)
        s.refresh(r2)
        s.add(
            Job(
                title="Alpha",
                company="Acme",
                score=90,
                source="lever",
                apply_url="https://a.com/1",
                run_id=r1.id,
            )
        )
        s.add(
            Job(
                title="Beta",
                company="Stripe",
                score=70,
                source="greenhouse",
                apply_url="https://a.com/2",
                run_id=r1.id,
            )
        )
        s.add(
            Job(
                title="Gamma",
                company="Acme",
                score=60,
                source="lever",
                apply_url="https://a.com/3",
                run_id=r2.id,
            )
        )
        s.commit()
        return r1.id, r2.id


def test_get_jobs_returns_grouped_shape(client, test_engine):
    _seed(test_engine)
    resp = client.get("/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert "run" in data[0]
    assert "jobs" in data[0]
    assert isinstance(data[0]["jobs"], list)


def test_get_jobs_newest_run_first(client, test_engine):
    r1_id, _ = _seed(test_engine)
    data = client.get("/jobs").json()
    assert data[0]["run"]["id"] == r1_id


def test_get_jobs_run_has_required_fields(client, test_engine):
    _seed(test_engine)
    run = client.get("/jobs").json()[0]["run"]
    for field in (
        "id",
        "started_at",
        "finished_at",
        "jobs_fetched",
        "jobs_qualified",
        "jobs_rejected",
    ):
        assert field in run, f"Missing run field: {field}"


def test_get_jobs_job_has_required_fields(client, test_engine):
    _seed(test_engine)
    job = client.get("/jobs").json()[0]["jobs"][0]
    for field in ("id", "title", "company", "score", "source", "apply_url", "run_id"):
        assert field in job, f"Missing job field: {field}"


def test_get_jobs_score_min_filter(client, test_engine):
    _seed(test_engine)
    data = client.get("/jobs?score_min=80").json()
    all_jobs = [j for g in data for j in g["jobs"]]
    assert len(all_jobs) == 1
    assert all(j["score"] >= 80 for j in all_jobs)


def test_get_jobs_source_filter(client, test_engine):
    _seed(test_engine)
    data = client.get("/jobs?source=lever").json()
    all_jobs = [j for g in data for j in g["jobs"]]
    assert all(j["source"] == "lever" for j in all_jobs)
    assert len(all_jobs) == 2


def test_get_jobs_company_filter_case_insensitive(client, test_engine):
    _seed(test_engine)
    data = client.get("/jobs?company=stripe").json()
    all_jobs = [j for g in data for j in g["jobs"]]
    assert len(all_jobs) == 1
    assert all_jobs[0]["company"] == "Stripe"


def test_get_jobs_empty_db(client):
    data = client.get("/jobs").json()
    assert data == []
