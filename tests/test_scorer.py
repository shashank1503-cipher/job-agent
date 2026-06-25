"""Unit tests for _score_job scoring components and pre-filters."""

import pytest
from agents.match_agent import _score_job, _parse_salary_lpa


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _job(**kwargs):
    base = {
        "title": "Senior Backend Engineer",
        "company": "Acme",
        "location": "Remote, India",
        "description": "We need a Python Backend engineer with REST API and FastAPI experience.",
        "salary": "",
    }
    base.update(kwargs)
    return base


def _prefs(**kwargs):
    base = {
        "roles": ["Senior Backend Engineer", "Backend Engineer"],
        "keywords_must_have": ["Python", "Backend", "REST API"],
        "keywords_nice_to_have": {
            "tier1": ["Django", "FastAPI", "Elasticsearch", "Microservices", "Kubernetes"],
            "tier2": ["Go", "React", "AWS", "Docker"],
        },
        "industry_keywords": {
            "Cybersecurity": ["security", "threat", "vulnerability"],
            "FinTech": ["fintech", "payments", "banking"],
        },
        "locations": ["Remote", "Bangalore"],
        "remote_locations": ["India", "IN"],
        "exclude_companies": ["BadCorp"],
        "keywords_exclude": ["PHP", ".NET"],
        "experience_years": {"min": 1, "max": 4},
        "min_salary_lpa": 28,
        "min_match_score": 70,
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Title scoring
# ---------------------------------------------------------------------------

_SENTINEL = ["__NOTFOUND__"]  # keyword never in any description, gives 0 must-have score


class TestTitleScore:
    def _iso(self):
        return _prefs(
            keywords_must_have=_SENTINEL,
            keywords_nice_to_have={},
            industry_keywords={},
            locations=[],
            remote_locations=[],
        )

    def test_full_match_gives_25(self):
        result = _score_job(_job(title="Senior Backend Engineer", description="", location=""), self._iso())
        assert result["score"] == 25

    def test_partial_match_gives_10(self):
        result = _score_job(_job(title="Backend Developer", description="", location=""), self._iso())
        assert result["score"] == 10

    def test_no_match_gives_0(self):
        result = _score_job(_job(title="Java Frontend Developer", description="", location=""), self._iso())
        assert result["score"] == 0

    def test_strong_title_match_in_reasons(self):
        result = _score_job(_job(title="Senior Backend Engineer"), _prefs())
        assert "Strong title match" in result["reasons"]

    def test_partial_title_match_in_reasons(self):
        result = _score_job(_job(title="Backend Developer"), _prefs())
        assert "Partial title match" in result["reasons"]


# ---------------------------------------------------------------------------
# Must-have keyword scoring
# ---------------------------------------------------------------------------

class TestMustHaveScore:
    def _isolated_prefs(self, must_have):
        return _prefs(
            keywords_must_have=must_have,
            keywords_nice_to_have={},
            industry_keywords={},
            locations=[],
            remote_locations=[],
            roles=[],
        )

    def test_all_must_haves_hit(self):
        prefs = self._isolated_prefs(["Python", "Backend"])
        job = _job(title="", description="Python Backend service", location="")
        result = _score_job(job, prefs)
        assert result["score"] == 30

    def test_half_must_haves_hit(self):
        prefs = self._isolated_prefs(["Python", "Backend"])
        job = _job(title="", description="Python service only", location="")
        result = _score_job(job, prefs)
        assert result["score"] == 15

    def test_no_must_haves_hit(self):
        prefs = self._isolated_prefs(["Python", "Backend", "REST API"])
        job = _job(title="", description="Java Spring developer", location="")
        result = _score_job(job, prefs)
        assert result["score"] == 0

    def test_missing_keywords_reported(self):
        prefs = self._isolated_prefs(["Python", "Backend", "REST API"])
        job = _job(title="", description="Python only", location="")
        result = _score_job(job, prefs)
        assert "Backend" in result["missing_keywords"]
        assert "REST API" in result["missing_keywords"]


# ---------------------------------------------------------------------------
# Tiered nice-to-have scoring
# ---------------------------------------------------------------------------

class TestNiceToHaveScore:
    def _isolated_prefs(self, tier1, tier2):
        return _prefs(
            keywords_must_have=_SENTINEL,
            keywords_nice_to_have={"tier1": tier1, "tier2": tier2},
            industry_keywords={},
            locations=[],
            remote_locations=[],
            roles=[],
        )

    def test_tier1_hit_worth_more_than_tier2(self):
        prefs_t1 = self._isolated_prefs(tier1=["Django"], tier2=["Go"])
        prefs_t2 = self._isolated_prefs(tier1=["Django"], tier2=["Go"])

        score_t1 = _score_job(_job(title="", description="Django service", location=""), prefs_t1)["score"]
        score_t2 = _score_job(_job(title="", description="Go service", location=""), prefs_t2)["score"]
        assert score_t1 > score_t2

    def test_all_tiers_hit_gives_20(self):
        prefs = self._isolated_prefs(tier1=["Django", "FastAPI"], tier2=["Go", "Docker"])
        job = _job(title="", description="Django FastAPI Go Docker", location="")
        result = _score_job(job, prefs)
        assert result["score"] == 20

    def test_backward_compat_flat_list(self):
        prefs = _prefs(
            keywords_must_have=_SENTINEL,
            keywords_nice_to_have=["Go", "Docker"],
            industry_keywords={},
            locations=[],
            remote_locations=[],
            roles=[],
        )
        job = _job(title="", description="Go Docker service", location="")
        result = _score_job(job, prefs)
        assert result["score"] == 20

    def test_nice_to_have_in_strengths(self):
        result = _score_job(
            _job(description="Python Backend REST API FastAPI service"),
            _prefs(),
        )
        assert "FastAPI" in result["strengths"]


# ---------------------------------------------------------------------------
# Industry scoring
# ---------------------------------------------------------------------------

class TestIndustryScore:
    def _isolated_prefs(self, industry_keywords):
        return _prefs(
            keywords_must_have=_SENTINEL,
            keywords_nice_to_have={},
            industry_keywords=industry_keywords,
            locations=[],
            remote_locations=[],
            roles=[],
        )

    def test_industry_keyword_match_gives_10(self):
        prefs = self._isolated_prefs({"FinTech": ["payments", "banking"]})
        job = _job(title="", description="Build our payments platform", location="")
        result = _score_job(job, prefs)
        assert result["score"] == 10

    def test_no_industry_match_gives_0(self):
        prefs = self._isolated_prefs({"FinTech": ["payments", "banking"]})
        job = _job(title="", description="Generic software company", location="")
        result = _score_job(job, prefs)
        assert result["score"] == 0

    def test_industry_reported_in_reasons(self):
        result = _score_job(
            _job(description="Python Backend REST API payments platform"),
            _prefs(),
        )
        assert any("FinTech" in r for r in result["reasons"])

    def test_first_matching_industry_wins(self):
        prefs = self._isolated_prefs({
            "FinTech": ["payments"],
            "Cybersecurity": ["security"],
        })
        job = _job(title="", description="payments security platform", location="")
        result = _score_job(job, prefs)
        assert result["score"] == 10  # only 10 regardless of two matches


# ---------------------------------------------------------------------------
# Location scoring
# ---------------------------------------------------------------------------

class TestLocationScore:
    def _isolated_prefs(self):
        return _prefs(
            keywords_must_have=_SENTINEL,
            keywords_nice_to_have={},
            industry_keywords={},
            remote_locations=[],
            roles=[],
        )

    def test_remote_gives_10(self):
        prefs = self._isolated_prefs()
        result = _score_job(_job(title="", description="", location="Remote"), prefs)
        assert result["score"] == 10

    def test_no_remote_gives_0(self):
        prefs = self._isolated_prefs()
        for loc in ["No remote", "Not remote", "no remote work"]:
            result = _score_job(_job(title="", description="", location=loc), prefs)
            assert result["score"] == 0, f"Expected 0 for location '{loc}'"

    def test_allowed_city_gives_10(self):
        prefs = self._isolated_prefs()
        result = _score_job(_job(title="", description="", location="Bangalore, India"), prefs)
        assert result["score"] == 10

    def test_hybrid_bangalore_gives_10(self):
        prefs = self._isolated_prefs()
        result = _score_job(_job(title="", description="", location="Hybrid in Bangalore"), prefs)
        assert result["score"] == 10

    def test_hybrid_unknown_city_gives_0(self):
        prefs = self._isolated_prefs()
        result = _score_job(_job(title="", description="", location="Hybrid in Mumbai"), prefs)
        assert result["score"] == 0

    def test_unknown_location_gives_0(self):
        prefs = self._isolated_prefs()
        result = _score_job(_job(title="", description="", location="Warsaw, Poland"), prefs)
        assert result["score"] == 0


# ---------------------------------------------------------------------------
# Pre-filter: excluded company
# ---------------------------------------------------------------------------

class TestPrefilterExcludedCompany:
    def test_excluded_company_rejected(self):
        result = _score_job(_job(company="BadCorp"), _prefs())
        assert result["score"] == 0
        assert "Excluded company" in result["reasons"][0]

    def test_excluded_company_case_insensitive(self):
        result = _score_job(_job(company="badcorp"), _prefs())
        assert result["score"] == 0

    def test_non_excluded_company_passes(self):
        result = _score_job(_job(company="GoodCorp"), _prefs())
        assert result["score"] > 0


# ---------------------------------------------------------------------------
# Pre-filter: excluded keywords
# ---------------------------------------------------------------------------

class TestPrefilterExcludedKeyword:
    def test_excluded_keyword_in_title_rejected(self):
        result = _score_job(_job(title="PHP Backend Engineer"), _prefs())
        assert result["score"] == 0
        assert "PHP" in result["reasons"][0]

    def test_excluded_keyword_in_description_head_rejected(self):
        result = _score_job(_job(description="This role requires PHP development"), _prefs())
        assert result["score"] == 0

    def test_excluded_keyword_deep_in_description_passes(self):
        # Keyword only mentioned deep in description (beyond 500 chars) should not reject
        long_prefix = "Python Backend REST API " * 25  # ~600 chars before the excluded keyword
        result = _score_job(_job(description=long_prefix + "Some mention of PHP"), _prefs())
        assert result["score"] > 0


# ---------------------------------------------------------------------------
# Pre-filter: experience gate
# ---------------------------------------------------------------------------

class TestPrefilterExperienceGate:
    def test_10_plus_years_rejected_when_max_4(self):
        job = _job(description="Requirements: 10+ years of experience in backend development.")
        result = _score_job(job, _prefs(experience_years={"min": 1, "max": 4}))
        assert result["score"] == 0
        assert "experience" in result["reasons"][0].lower()

    def test_8_plus_years_rejected_when_max_4(self):
        job = _job(description="Minimum 8+ years in software engineering required.")
        result = _score_job(job, _prefs(experience_years={"min": 1, "max": 4}))
        assert result["score"] == 0

    def test_5_years_not_rejected(self):
        job = _job(description="5+ years of Python experience preferred.")
        result = _score_job(job, _prefs(experience_years={"min": 1, "max": 4}))
        assert result["score"] > 0

    def test_experience_gate_skipped_when_max_high(self):
        job = _job(description="10+ years of experience required.")
        result = _score_job(job, _prefs(experience_years={"min": 5, "max": 15}))
        assert result["score"] > 0


# ---------------------------------------------------------------------------
# Pre-filter: salary gate
# ---------------------------------------------------------------------------

class TestPrefilterSalaryGate:
    def test_salary_below_min_rejected(self):
        job = _job(salary="20 LPA")
        result = _score_job(job, _prefs(min_salary_lpa=28))
        assert result["score"] == 0
        assert "Salary" in result["reasons"][0]

    def test_salary_above_min_passes(self):
        job = _job(salary="35 LPA")
        result = _score_job(job, _prefs(min_salary_lpa=28))
        assert result["score"] > 0

    def test_missing_salary_passes(self):
        job = _job(salary="")
        result = _score_job(job, _prefs(min_salary_lpa=28))
        assert result["score"] > 0

    def test_unparseable_salary_passes(self):
        job = _job(salary="Competitive")
        result = _score_job(job, _prefs(min_salary_lpa=28))
        assert result["score"] > 0


# ---------------------------------------------------------------------------
# Pre-filter: remote location
# ---------------------------------------------------------------------------

class TestPrefilterRemoteLocation:
    def test_non_india_remote_rejected(self):
        for loc in ["Argentina, Remote", "Remote in the US", "Remote - UK", "Brazil, Remote"]:
            result = _score_job(_job(location=loc), _prefs())
            assert result["score"] == 0, f"Expected rejection for '{loc}'"

    def test_india_remote_passes(self):
        for loc in ["India, Remote", "Remote, India", "Remote, IN"]:
            result = _score_job(_job(location=loc), _prefs())
            assert result["score"] > 0, f"Expected pass for '{loc}'"

    def test_plain_remote_passes(self):
        result = _score_job(_job(location="Remote"), _prefs())
        assert result["score"] > 0

    def test_remote_in_the_us_rejected_not_matched_by_IN(self):
        result = _score_job(_job(location="Remote in the US"), _prefs())
        assert result["score"] == 0


# ---------------------------------------------------------------------------
# _parse_salary_lpa
# ---------------------------------------------------------------------------

class TestParseSalaryLpa:
    def test_lpa_suffix(self):
        assert _parse_salary_lpa("28 LPA") == 28.0

    def test_lakh_suffix(self):
        assert _parse_salary_lpa("30 lakhs") == 30.0

    def test_plain_number_in_range(self):
        assert _parse_salary_lpa("35") == 35.0

    def test_empty_returns_none(self):
        assert _parse_salary_lpa("") is None

    def test_text_only_returns_none(self):
        assert _parse_salary_lpa("Competitive") is None
