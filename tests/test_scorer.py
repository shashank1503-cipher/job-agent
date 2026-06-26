"""Unit tests for match_agent scoring components, pre-filters, and BM25+BERT pipeline."""

import pytest
from unittest.mock import MagicMock, patch

from agents.match_agent import (
    _score_job,
    _parse_salary_lpa,
    _build_bm25_query_tokens,
    _minmax_normalize,
    _norm,
    MatchAgent,
)


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
            "tier1": [
                "Django",
                "FastAPI",
                "Elasticsearch",
                "Microservices",
                "Kubernetes",
            ],
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

_SENTINEL = [
    "__NOTFOUND__"
]  # keyword never in any description, gives 0 must-have score


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
        result = _score_job(
            _job(title="Senior Backend Engineer", description="", location=""),
            self._iso(),
        )
        assert result["score"] == 25

    def test_partial_match_gives_10(self):
        # "Senior Backend Developer" matches "senior" and "backend" from "Senior Backend Engineer" → ≥2 words
        result = _score_job(
            _job(title="Senior Backend Developer", description="", location=""),
            self._iso(),
        )
        assert result["score"] == 10

    def test_single_meaningful_word_scores_0(self):
        # "Backend Developer" shares only "backend" with any role — 1 word, below the ≥2 threshold
        result = _score_job(
            _job(title="Backend Developer", description="", location=""), self._iso()
        )
        assert result["score"] == 0

    def test_no_match_gives_0(self):
        result = _score_job(
            _job(title="Java Frontend Developer", description="", location=""),
            self._iso(),
        )
        assert result["score"] == 0

    def test_strong_title_match_in_reasons(self):
        result = _score_job(_job(title="Senior Backend Engineer"), _prefs())
        assert "Strong title match" in result["reasons"]

    def test_partial_title_match_in_reasons(self):
        result = _score_job(_job(title="Senior Backend Developer"), _prefs())
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

        score_t1 = _score_job(
            _job(title="", description="Django service", location=""), prefs_t1
        )["score"]
        score_t2 = _score_job(
            _job(title="", description="Go service", location=""), prefs_t2
        )["score"]
        assert score_t1 > score_t2

    def test_all_tiers_hit_gives_20(self):
        prefs = self._isolated_prefs(
            tier1=["Django", "FastAPI"], tier2=["Go", "Docker"]
        )
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

    def test_industries_flat_list_triggers_match(self):
        # No industry_keywords — match should come from the industries flat list
        prefs = _prefs(
            keywords_must_have=_SENTINEL,
            keywords_nice_to_have={},
            industry_keywords={},
            industries=["FinTech", "SaaS"],
            locations=[],
            remote_locations=[],
            roles=[],
        )
        job = _job(
            title="",
            description="Build SaaS products for enterprise clients",
            location="",
        )
        result = _score_job(job, prefs)
        assert result["score"] == 10
        assert any("SaaS" in r for r in result["reasons"])

    def test_industry_reported_in_reasons(self):
        result = _score_job(
            _job(description="Python Backend REST API payments platform"),
            _prefs(),
        )
        assert any("FinTech" in r for r in result["reasons"])

    def test_first_matching_industry_wins(self):
        prefs = self._isolated_prefs(
            {
                "FinTech": ["payments"],
                "Cybersecurity": ["security"],
            }
        )
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
        result = _score_job(
            _job(title="", description="", location="Bangalore, India"), prefs
        )
        assert result["score"] == 10

    def test_hybrid_bangalore_gives_10(self):
        prefs = self._isolated_prefs()
        result = _score_job(
            _job(title="", description="", location="Hybrid in Bangalore"), prefs
        )
        assert result["score"] == 10

    def test_hybrid_unknown_city_gives_0(self):
        prefs = self._isolated_prefs()
        result = _score_job(
            _job(title="", description="", location="Hybrid in Mumbai"), prefs
        )
        assert result["score"] == 0

    def test_unknown_location_gives_0(self):
        prefs = self._isolated_prefs()
        result = _score_job(
            _job(title="", description="", location="Warsaw, Poland"), prefs
        )
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
        result = _score_job(
            _job(description="This role requires PHP development"), _prefs()
        )
        assert result["score"] == 0

    def test_excluded_keyword_deep_in_description_rejects(self):
        # Exclusion scans full description — keyword past 500 chars must still reject
        long_prefix = (
            "Python Backend REST API " * 25
        )  # ~600 chars before the excluded keyword
        result = _score_job(
            _job(description=long_prefix + "Some mention of PHP"), _prefs()
        )
        assert result["score"] == 0


# ---------------------------------------------------------------------------
# Pre-filter: experience gate
# ---------------------------------------------------------------------------


class TestPrefilterExperienceGate:
    def test_10_plus_years_rejected_when_max_4(self):
        job = _job(
            description="Requirements: 10+ years of experience in backend development."
        )
        result = _score_job(job, _prefs(experience_years={"min": 1, "max": 4}))
        assert result["score"] == 0
        assert "experience" in result["reasons"][0].lower()

    def test_8_plus_years_rejected_when_max_4(self):
        job = _job(description="Minimum 8+ years in software engineering required.")
        result = _score_job(job, _prefs(experience_years={"min": 1, "max": 4}))
        assert result["score"] == 0

    def test_5_plus_years_rejected_when_max_4(self):
        job = _job(description="5+ years of Python experience required.")
        result = _score_job(job, _prefs(experience_years={"min": 1, "max": 4}))
        assert result["score"] == 0

    def test_6_plus_years_rejected_when_max_4(self):
        job = _job(description="Minimum 6 years in backend engineering required.")
        result = _score_job(job, _prefs(experience_years={"min": 1, "max": 4}))
        assert result["score"] == 0

    def test_7_plus_years_rejected_when_max_4(self):
        job = _job(description="We need someone with 7+ years of experience.")
        result = _score_job(job, _prefs(experience_years={"min": 1, "max": 4}))
        assert result["score"] == 0

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
        for loc in [
            "Argentina, Remote",
            "Remote in the US",
            "Remote - UK",
            "Brazil, Remote",
        ]:
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
# Pre-filter: exclude_locations
# ---------------------------------------------------------------------------

_EXCLUDE_LOCS = [
    "USA",
    "United States",
    "US",
    "UK",
    "United Kingdom",
    "Singapore",
    "Europe",
    "Canada",
]


class TestPrefilterExcludeLocations:
    def _prefs_ex(self, **kwargs):
        return _prefs(exclude_locations=_EXCLUDE_LOCS, **kwargs)

    def test_usa_in_location_rejected(self):
        result = _score_job(_job(location="New York, USA"), self._prefs_ex())
        assert result["score"] == 0
        assert "Excluded location" in result["reasons"][0]

    def test_remote_us_rejected(self):
        result = _score_job(_job(location="Remote - US"), self._prefs_ex())
        assert result["score"] == 0
        assert "Excluded location" in result["reasons"][0]

    def test_india_location_not_rejected(self):
        result = _score_job(_job(location="Bangalore, India"), self._prefs_ex())
        assert result["score"] > 0

    def test_plain_remote_no_country_not_rejected(self):
        result = _score_job(_job(location="Remote"), self._prefs_ex())
        assert result["score"] > 0

    def test_exclude_location_wins_before_remote_location_check(self):
        # remote_locations allows only India, but exclude_locations should fire first
        result = _score_job(_job(location="Remote - UK"), self._prefs_ex())
        assert result["score"] == 0
        assert "Excluded location" in result["reasons"][0]

    def test_no_exclude_locations_key_is_noop(self):
        # prefs without exclude_locations must not raise or reject
        result = _score_job(_job(location="New York, USA"), _prefs())
        # remote_locations filter may still reject it, but not because of exclude_locations
        assert "Excluded location" not in (
            result["reasons"][0] if result["reasons"] else ""
        )

    def test_russia_not_false_positive_for_us(self):
        # "russia" contains the substring "us" — word-boundary matching must not reject it
        result = _score_job(_job(location="Russia, Remote"), self._prefs_ex())
        # remote_locations may reject (not India) — but reason must NOT be exclude_locations
        assert "Excluded location" not in (
            result["reasons"][0] if result["reasons"] else ""
        )


# ---------------------------------------------------------------------------
# match_analysis shape (_score_job direct)
# ---------------------------------------------------------------------------


class TestMatchAnalysisShape:
    _REQUIRED_KEYS = {
        "score",
        "title_score",
        "must_score",
        "nice_score",
        "industry_score",
        "location_score",
        "reasons",
        "missing_keywords",
        "strengths",
    }

    def test_passing_job_has_all_keys(self):
        # title=25, must=30, nice≈3 (FastAPI tier1), industry=10 (payments→FinTech), loc=10 → 78
        job = _job(description="Python Backend REST API FastAPI payments platform")
        result = _score_job(job, _prefs())
        assert result.keys() >= self._REQUIRED_KEYS

    def test_passing_job_component_scores(self):
        job = _job(description="Python Backend REST API FastAPI payments platform")
        result = _score_job(job, _prefs())
        assert result["title_score"] == 25
        assert result["must_score"] == 30
        assert result["nice_score"] == 3  # 2/14 * 20 ≈ 2.86 → round → 3
        assert result["industry_score"] == 10
        assert result["location_score"] == 10
        assert result["score"] == 78

    def test_rejected_job_has_all_keys(self):
        result = _score_job(_job(company="BadCorp"), _prefs())
        assert result.keys() >= self._REQUIRED_KEYS

    def test_rejected_job_component_scores_are_zero(self):
        result = _score_job(_job(company="BadCorp"), _prefs())
        assert result["score"] == 0
        assert result["title_score"] == 0
        assert result["must_score"] == 0
        assert result["nice_score"] == 0
        assert result["industry_score"] == 0
        assert result["location_score"] == 0


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


# ---------------------------------------------------------------------------
# BM25 query token building
# ---------------------------------------------------------------------------


class TestBuildBM25QueryTokens:
    def test_must_have_tokens_repeated_3x(self):
        prefs = _prefs(
            keywords_must_have=["Python"], keywords_nice_to_have={}, roles=[]
        )
        tokens = _build_bm25_query_tokens(prefs)
        assert tokens.count("python") == 3

    def test_tier1_tokens_repeated_2x(self):
        prefs = _prefs(
            keywords_must_have=[],
            keywords_nice_to_have={"tier1": ["FastAPI"], "tier2": []},
            roles=[],
        )
        tokens = _build_bm25_query_tokens(prefs)
        assert tokens.count("fastapi") == 2

    def test_tier2_tokens_repeated_1x(self):
        prefs = _prefs(
            keywords_must_have=[],
            keywords_nice_to_have={"tier1": [], "tier2": ["Go"]},
            roles=[],
        )
        tokens = _build_bm25_query_tokens(prefs)
        assert tokens.count("go") == 1

    def test_multiword_keyword_split_correctly(self):
        prefs = _prefs(
            keywords_must_have=["REST API"], keywords_nice_to_have={}, roles=[]
        )
        tokens = _build_bm25_query_tokens(prefs)
        assert tokens.count("rest") == 3
        assert tokens.count("api") == 3

    def test_flat_nice_list_repeated_1x(self):
        prefs = _prefs(
            keywords_must_have=[],
            keywords_nice_to_have=["Go", "Docker"],
            roles=[],
        )
        tokens = _build_bm25_query_tokens(prefs)
        assert tokens.count("go") == 1
        assert tokens.count("docker") == 1


# ---------------------------------------------------------------------------
# _minmax_normalize
# ---------------------------------------------------------------------------


class TestMinmaxNormalize:
    def test_min_maps_to_lo_max_maps_to_hi(self):
        result = _minmax_normalize([0.0, 5.0, 10.0], 0, 30)
        assert result[0] == pytest.approx(0.0)
        assert result[-1] == pytest.approx(30.0)

    def test_all_same_scores_returns_midpoint(self):
        result = _minmax_normalize([5.0, 5.0, 5.0], 0, 40)
        assert all(s == pytest.approx(20.0) for s in result)

    def test_empty_returns_empty(self):
        assert _minmax_normalize([], 0, 30) == []

    def test_bm25_output_in_range_0_30(self):
        from rank_bm25 import BM25Okapi

        prefs = _prefs()
        tokens = _build_bm25_query_tokens(prefs)
        corpus = [
            _norm("Python FastAPI Backend REST API Microservices").split(),
            _norm("Java Spring Boot developer team").split(),
        ]
        bm25 = BM25Okapi(corpus)
        scores = list(bm25.get_scores(tokens))
        normalized = _minmax_normalize(scores, 0, 30)
        assert all(0 <= s <= 30 for s in normalized)

    def test_jobbert_output_in_range_0_40(self):
        raw = [-5.0, -1.0, 0.5, 3.0, 8.0]
        normalized = _minmax_normalize(raw, 0, 40)
        assert all(0 <= s <= 40 for s in normalized)
        assert min(normalized) == pytest.approx(0.0)
        assert max(normalized) == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# Dense > sparse BM25
# ---------------------------------------------------------------------------


class TestBM25DenseVsSparse:
    def test_dense_keyword_match_scores_higher_than_sparse(self):
        from rank_bm25 import BM25Okapi

        prefs = _prefs()
        tokens = _build_bm25_query_tokens(prefs)
        dense = _norm(
            "Python FastAPI Backend REST API Microservices Docker Go Django"
        ).split()
        sparse = _norm("Java developer team building products").split()
        # Add filler docs so IDF is meaningful for terms unique to the dense doc
        filler = ["lorem ipsum dolor sit amet consectetur".split()] * 8
        bm25 = BM25Okapi([dense, sparse] + filler)
        scores = bm25.get_scores(tokens)
        assert scores[0] > scores[1]


# ---------------------------------------------------------------------------
# MatchAgent pipeline tests (mocked SentenceTransformer + parsed_resume)
# ---------------------------------------------------------------------------

_SAMPLE_RESUME = {
    "skills": ["Python", "FastAPI", "Backend"],
    "years": 3,
    "level": "mid",
    "industries": ["SaaS"],
    "roles": ["Backend Engineer"],
}


def _make_agent(prefs, resume=None):
    """Create MatchAgent with mocked SentenceTransformer and _load_parsed_resume."""
    resume = resume or _SAMPLE_RESUME
    mock_model = MagicMock()
    with (
        patch("agents.match_agent.SentenceTransformer", return_value=mock_model),
        patch.object(MatchAgent, "_load_parsed_resume", return_value=resume),
    ):
        return MatchAgent(prefs)


class TestBM25Recall:
    def test_job_outside_top_150_rejected_with_correct_reason(self):
        # 150 keyword-rich jobs, 1 unrelated job at the end
        rich_jobs = [
            _job(
                title=f"Python Backend Engineer {i}",
                description="Python FastAPI Backend REST API Microservices",
            )
            for i in range(150)
        ]
        sparse_job = _job(
            title="Unrelated Role", description="Lorem ipsum dolor sit amet"
        )
        all_jobs = rich_jobs + [sparse_job]

        agent = _make_agent(_prefs())
        with patch("agents.match_agent.util") as mock_util:
            mock_util.cos_sim.return_value = [[0.0] * 150]
            agent.run(all_jobs)

        analysis = sparse_job.get("match_analysis", {})
        assert analysis.get("score") == 0
        assert analysis.get("reasons") == ["below BM25 recall threshold"]

    def test_top_150_bm25_scores_in_range_0_30(self):
        jobs = [
            _job(description="Python Backend FastAPI REST API Microservices"),
            _job(description="Go microservices backend engineer"),
            _job(description="Java Spring developer unrelated"),
        ]
        agent = _make_agent(_prefs())
        with patch("agents.match_agent.util") as mock_util:
            mock_util.cos_sim.return_value = [[0.0, 0.0, 0.0]]
            agent.run(jobs)
        for job in jobs:
            bm25_s = job["match_analysis"].get("bm25_score", -1)
            assert 0 <= bm25_s <= 30, f"bm25_score out of range: {bm25_s}"


class TestBlendedScore:
    def test_match_analysis_contains_bm25_and_jobbert_keys(self):
        job = _job(description="Python Backend REST API FastAPI Microservices")
        agent = _make_agent(_prefs())
        with patch("agents.match_agent.util") as mock_util:
            mock_util.cos_sim.return_value = [[5.0]]
            agent.run([job])
        keys = job["match_analysis"].keys()
        for k in (
            "score",
            "bm25_score",
            "jobbert_score",
            "title_score",
            "industry_score",
            "location_score",
            "reasons",
            "missing_keywords",
            "strengths",
        ):
            assert k in keys, f"Missing key in match_analysis: {k}"

    def test_jobbert_score_in_range_0_40(self):
        jobs = [
            _job(description="Python Backend REST API"),
            _job(description="Java Spring developer"),
        ]
        agent = _make_agent(_prefs())
        with patch("agents.match_agent.util") as mock_util:
            mock_util.cos_sim.return_value = [[2.0, -1.0]]
            agent.run(jobs)
        for job in jobs:
            jobbert_s = job["match_analysis"].get("jobbert_score", -1)
            assert 0 <= jobbert_s <= 40, f"jobbert_score out of range: {jobbert_s}"

    def test_final_score_is_sum_of_5_components(self):
        job = _job(
            title="Senior Backend Engineer",
            description="Python Backend REST API FastAPI payments platform",
        )
        agent = _make_agent(_prefs())
        with patch("agents.match_agent.util") as mock_util:
            mock_util.cos_sim.return_value = [[3.0]]
            agent.run([job])
        a = job["match_analysis"]
        expected = min(
            100,
            a["bm25_score"]
            + a["jobbert_score"]
            + a["title_score"]
            + a["industry_score"]
            + a["location_score"],
        )
        assert a["score"] == expected

    def test_final_score_capped_at_100(self):
        job = _job(
            description="Python Backend REST API FastAPI Microservices Kubernetes Docker Go AWS"
        )
        agent = _make_agent(_prefs())
        with patch("agents.match_agent.util") as mock_util:
            mock_util.cos_sim.return_value = [[100.0]]
            agent.run([job])
        assert job["match_analysis"]["score"] <= 100

    def test_pre_filter_rejected_job_has_score_0_in_top_150(self):
        excluded_job = _job(
            company="BadCorp", description="Python Backend REST API FastAPI"
        )
        agent = _make_agent(_prefs())
        with patch("agents.match_agent.util") as mock_util:
            mock_util.cos_sim.return_value = [[5.0]]
            agent.run([excluded_job])
        assert excluded_job["match_analysis"]["score"] == 0
        assert "Excluded company" in excluded_job["match_analysis"]["reasons"][0]


class TestMatchAgentInit:
    def test_missing_parsed_resume_raises_file_not_found(self):
        with patch("agents.match_agent.Path") as mock_path_cls:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_path_cls.return_value = mock_path
            with pytest.raises(FileNotFoundError):
                MatchAgent(_prefs())

    def test_missing_parsed_resume_does_not_silently_fall_back(self):
        # Must raise, not return an empty dict or default
        with patch("agents.match_agent.Path") as mock_path_cls:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_path_cls.return_value = mock_path
            raised = False
            try:
                MatchAgent(_prefs())
            except FileNotFoundError:
                raised = True
            except Exception:
                pass  # any other exception also means it didn't silently fall back
            assert raised, "Expected FileNotFoundError but got no exception"
