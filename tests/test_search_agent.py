"""Smoke tests for the multi-source search_agent."""

import pandas as pd
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_spy_df(rows=None):
    default = [
        {
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Remote",
            "description": "Python FastAPI backend role.",
            "job_url": "https://example.com/job/linkedin/1",
            "min_amount": "30",
            "date_posted": "2024-01-01",
            "site": "linkedin",
        },
        {
            "title": "Senior Backend Engineer",
            "company": "Beta Corp",
            "location": "Bangalore",
            "description": "Django REST microservices.",
            "job_url": "https://example.com/job/indeed/2",
            "min_amount": "",
            "date_posted": "2024-01-02",
            "site": "indeed",
        },
    ]
    return pd.DataFrame(rows if rows is not None else default)


def _make_gh_jobs():
    return [
        {
            "title": "Software Engineer II",
            "company": "GHCorp",
            "location": "San Francisco, CA",
            "description": "Greenhouse Python backend role.",
            "url": "https://boards.greenhouse.io/ghcorp/jobs/100",
            "salary": "",
            "date_posted": "2024-01-03T00:00:00Z",
            "source": "greenhouse",
        }
    ]


def _make_lv_jobs():
    return [
        {
            "title": "Backend Developer",
            "company": "leverco",
            "location": "Remote",
            "description": "Lever Python microservices.",
            "url": "https://jobs.lever.co/leverco/abc123",
            "salary": "",
            "date_posted": "",
            "source": "lever",
        }
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@patch("agents.search_agent.fetch_lever_jobs")
@patch("agents.search_agent.fetch_greenhouse_jobs")
@patch("agents.search_agent.load_companies")
@patch("agents.search_agent.scrape_jobs")
def test_all_three_sources_contribute(mock_scrape, mock_load, mock_gh, mock_lv):
    mock_scrape.return_value = _make_spy_df()
    mock_load.return_value = {"greenhouse": ["ghcorp"], "lever": ["leverco"]}
    mock_gh.return_value = _make_gh_jobs()
    mock_lv.return_value = _make_lv_jobs()

    from agents.search_agent import search_jobs
    jobs = search_jobs("data/preferences.yaml")

    sources = {j["source"] for j in jobs}
    assert "linkedin" in sources, "Expected linkedin jobs"
    assert "indeed" in sources, "Expected indeed jobs"
    assert "greenhouse" in sources, "Expected greenhouse jobs"
    assert "lever" in sources, "Expected lever jobs"


@patch("agents.search_agent.fetch_lever_jobs")
@patch("agents.search_agent.fetch_greenhouse_jobs")
@patch("agents.search_agent.load_companies")
@patch("agents.search_agent.scrape_jobs")
def test_deduplication_same_url_two_sources(mock_scrape, mock_load, mock_gh, mock_lv):
    """Same URL appearing in both jobspy and greenhouse → only one entry."""
    shared_url = "https://boards.greenhouse.io/acme/jobs/999"
    spy_rows = [
        {
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Remote",
            "description": "Python backend role.",
            "job_url": shared_url,
            "min_amount": "",
            "date_posted": "2024-01-01",
            "site": "linkedin",
        }
    ]
    gh_rows = [
        {
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Remote",
            "description": "Python backend role from GH.",
            "url": shared_url,
            "salary": "",
            "date_posted": "",
            "source": "greenhouse",
        }
    ]
    mock_scrape.return_value = pd.DataFrame(spy_rows)
    mock_load.return_value = {"greenhouse": ["acme"], "lever": []}
    mock_gh.return_value = gh_rows
    mock_lv.return_value = []

    from agents.search_agent import search_jobs
    jobs = search_jobs("data/preferences.yaml")

    urls = [j["url"] for j in jobs]
    assert urls.count(shared_url) == 1, "Duplicate URL not deduplicated"
    assert len(urls) == len(set(urls)), "Found duplicate URLs in output"


@patch("agents.search_agent.fetch_lever_jobs")
@patch("agents.search_agent.fetch_greenhouse_jobs")
@patch("agents.search_agent.load_companies")
@patch("agents.search_agent.scrape_jobs")
def test_skips_empty_description(mock_scrape, mock_load, mock_gh, mock_lv):
    spy_rows = [
        {
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Remote",
            "description": "",   # empty — should be skipped
            "job_url": "https://example.com/job/3",
            "min_amount": "",
            "date_posted": "2024-01-01",
            "site": "linkedin",
        }
    ]
    gh_rows = [
        {
            "title": "SDE II",
            "company": "ghco",
            "location": "",
            "description": "",   # empty — should be skipped
            "url": "https://boards.greenhouse.io/ghco/jobs/1",
            "salary": "",
            "date_posted": "",
            "source": "greenhouse",
        }
    ]
    lv_rows = [
        {
            "title": "Backend Dev",
            "company": "lvco",
            "location": "",
            "description": "",   # empty — should be skipped
            "url": "https://jobs.lever.co/lvco/xyz",
            "salary": "",
            "date_posted": "",
            "source": "lever",
        }
    ]
    mock_scrape.return_value = pd.DataFrame(spy_rows)
    mock_load.return_value = {"greenhouse": ["ghco"], "lever": ["lvco"]}
    mock_gh.return_value = gh_rows
    mock_lv.return_value = lv_rows

    from agents.search_agent import search_jobs
    jobs = search_jobs("data/preferences.yaml")

    assert len(jobs) == 0, "Expected all empty-description jobs to be skipped"


@patch("agents.search_agent.fetch_lever_jobs")
@patch("agents.search_agent.fetch_greenhouse_jobs")
@patch("agents.search_agent.load_companies")
@patch("agents.search_agent.scrape_jobs")
def test_normalization_fields(mock_scrape, mock_load, mock_gh, mock_lv):
    """Every job dict must carry the standard set of fields."""
    mock_scrape.return_value = _make_spy_df()
    mock_load.return_value = {"greenhouse": ["ghcorp"], "lever": ["leverco"]}
    mock_gh.return_value = _make_gh_jobs()
    mock_lv.return_value = _make_lv_jobs()

    from agents.search_agent import search_jobs
    jobs = search_jobs("data/preferences.yaml")

    required = {"title", "company", "location", "description", "url", "salary",
                "date_posted", "source"}
    for job in jobs:
        missing = required - job.keys()
        assert not missing, f"Job missing fields: {missing} — {job.get('title')}"
