import json
import os
import re
from pathlib import Path

from rank_bm25 import BM25Okapi
from rich.console import Console
from rich.table import Table
from sentence_transformers import SentenceTransformer, util

console = Console()

# Matches experience requirements like "5+ years", "8+ years", "minimum 6 years"
_EXP_GATE = re.compile(
    r"\b(5|6|7|8|9|10|11|12|15)\+\s*years?\b"
    r"|\bminimum\s+(?:of\s+)?(5|6|7|8|9|10|11|12|15)\s*years?\b",
    re.IGNORECASE,
)

_NO_REMOTE = re.compile(r"\bnot?\s+remote\b", re.IGNORECASE)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", text.lower())


def _hits(text_norm: str, keywords: list) -> list:
    return [kw for kw in keywords if _norm(kw) in text_norm]


def _parse_salary_lpa(salary_str: str) -> float | None:
    if not salary_str:
        return None
    s = salary_str.lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:lpa|l\.p\.a|lakh)", s)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if m:
        val = float(m.group(1))
        if 5 <= val <= 200:
            return val
    return None


def _build_bm25_query_tokens(prefs: dict) -> list:
    """Build weighted token list for BM25 query from preferences."""
    tokens = []
    for kw in prefs.get("keywords_must_have", []):
        tokens.extend(_norm(kw).split() * 3)
    nice = prefs.get("keywords_nice_to_have", {})
    if isinstance(nice, dict):
        for kw in nice.get("tier1", []):
            tokens.extend(_norm(kw).split() * 2)
        for kw in nice.get("tier2", []):
            tokens.extend(_norm(kw).split())
    else:
        for kw in nice:
            tokens.extend(_norm(kw).split())
    for role in prefs.get("roles", []):
        tokens.extend(_norm(role).split())
    return tokens


def _minmax_normalize(scores: list, lo: float, hi: float) -> list:
    """Min-max normalize a list of scores to [lo, hi]."""
    if not scores:
        return []
    mn, mx = min(scores), max(scores)
    if mx == mn:
        return [(lo + hi) / 2] * len(scores)
    return [lo + (s - mn) / (mx - mn) * (hi - lo) for s in scores]


def _score_job(job: dict, prefs: dict) -> dict:
    title = job.get("title", "")
    company = job.get("company", "")
    location = job.get("location", "")
    description = job.get("description", "")

    title_norm = _norm(title)
    company_norm = company.lower().strip()
    loc_norm = _norm(location)
    full_norm = _norm(f"{title} {description}")

    # ── Hard disqualifiers ────────────────────────────────────────────────
    exclude_companies = {c.lower() for c in prefs.get("exclude_companies", [])}
    _zero = {
        "score": 0,
        "title_score": 0,
        "must_score": 0,
        "nice_score": 0,
        "industry_score": 0,
        "location_score": 0,
        "missing_keywords": [],
        "strengths": [],
        "pre_filtered": True,
    }

    if company_norm in exclude_companies:
        return {**_zero, "reasons": [f"Excluded company: {company}"]}

    for term in prefs.get("exclude_locations", []):
        term_norm = _norm(term)
        if len(term_norm) <= 3:
            matched = bool(re.search(r"\b" + re.escape(term_norm) + r"\b", loc_norm))
        else:
            matched = term_norm in loc_norm
        if matched:
            return {**_zero, "reasons": [f"Excluded location: {location}"]}

    for kw in prefs.get("keywords_exclude", []):
        if _norm(kw) in full_norm:
            return {**_zero, "reasons": [f"Excluded keyword in posting: {kw}"]}

    max_exp = prefs.get("experience_years", {}).get("max", 99)
    m = _EXP_GATE.search(description)
    if m:
        required = int(next(g for g in m.groups() if g is not None))
        if required > max_exp:
            return {**_zero, "reasons": [f"Requires {m.group(0).strip()} experience"]}

    min_salary = prefs.get("min_salary_lpa")
    if min_salary:
        salary_lpa = _parse_salary_lpa(job.get("salary", ""))
        if salary_lpa is not None and salary_lpa < min_salary:
            return {
                **_zero,
                "reasons": [f"Salary {salary_lpa} LPA below minimum {min_salary} LPA"],
            }

    remote_locations = prefs.get("remote_locations", [])
    if remote_locations and "remote" in loc_norm:
        loc_without_remote = loc_norm.replace("remote", "").strip()
        if loc_without_remote:
            loc_words = set(loc_without_remote.split())

            def _region_match(region):
                if len(region) <= 3:
                    return bool(re.search(r"\b" + re.escape(region) + r"\b", location))
                return _norm(region) in loc_words

            if not any(_region_match(r) for r in remote_locations):
                return {
                    **_zero,
                    "reasons": [f"Remote job outside allowed region: {location}"],
                }

    # ── Title match (0–25) ────────────────────────────────────────────────
    title_score = 0
    for role in prefs.get("roles", []):
        role_words = _norm(role).split()
        if all(w in title_norm for w in role_words):
            title_score = 25
            break
        meaningful = [w for w in role_words if len(w) > 3]
        matched_meaningful = [w for w in meaningful if w in title_norm]
        if len(matched_meaningful) >= 2:
            title_score = max(title_score, 10)

    # ── Must-have keywords (0–30) ─────────────────────────────────────────
    must_have = prefs.get("keywords_must_have", [])
    must_hits = _hits(full_norm, must_have)
    must_score = (len(must_hits) / len(must_have) * 30) if must_have else 30

    # ── Nice-to-have keywords (0–20, tiered) ──────────────────────────────
    nice_cfg = prefs.get("keywords_nice_to_have", [])
    if isinstance(nice_cfg, dict):
        tier1 = nice_cfg.get("tier1", [])
        tier2 = nice_cfg.get("tier2", [])
    else:
        tier1, tier2 = [], nice_cfg  # backward compat: flat list → all tier2

    tier1_hits = _hits(full_norm, tier1)
    tier2_hits = _hits(full_norm, tier2)
    max_weight = len(tier1) * 2 + len(tier2)
    hit_weight = len(tier1_hits) * 2 + len(tier2_hits)
    nice_score = (hit_weight / max_weight * 20) if max_weight > 0 else 0

    # ── Industry match (0–10) ─────────────────────────────────────────────
    industry_score = 0
    matched_industry = None
    for industry, keywords in prefs.get("industry_keywords", {}).items():
        if any(_norm(kw) in full_norm for kw in keywords):
            industry_score = 10
            matched_industry = industry
            break
    if industry_score == 0:
        for ind in prefs.get("industries", []):
            if _norm(ind) in full_norm:
                industry_score = 10
                matched_industry = ind
                break

    # ── Location match (0–10) ─────────────────────────────────────────────
    loc_score = 0
    if "remote" in loc_norm and not _NO_REMOTE.search(location):
        loc_score = 10
    elif "hybrid" in loc_norm:
        for dloc in prefs.get("locations", []):
            dloc_norm = _norm(dloc)
            if dloc_norm != "remote" and (
                dloc_norm in loc_norm or loc_norm in dloc_norm
            ):
                loc_score = 10
                break
    else:
        for dloc in prefs.get("locations", []):
            dloc_norm = _norm(dloc)
            if dloc_norm != "remote" and (
                dloc_norm in loc_norm or loc_norm in dloc_norm
            ):
                loc_score = 10
                break

    total = round(title_score + must_score + nice_score + industry_score + loc_score)
    score = min(100, total)

    # ── Human-readable reasons ────────────────────────────────────────────
    reasons = []
    if title_score >= 25:
        reasons.append("Strong title match")
    elif title_score > 0:
        reasons.append("Partial title match")
    if must_have:
        reasons.append(f"{len(must_hits)}/{len(must_have)} must-have keywords matched")
    all_nice_hits = tier1_hits + [h for h in tier2_hits if h not in tier1_hits]
    if all_nice_hits:
        reasons.append(f"{len(all_nice_hits)} nice-to-have keywords found")
    if matched_industry:
        reasons.append(f"Industry match: {matched_industry}")
    if loc_score:
        reasons.append(f"Location OK ({location})")

    missing = [kw for kw in must_have if kw not in must_hits]
    strengths = must_hits + [kw for kw in all_nice_hits if kw not in must_hits]

    return {
        "score": score,
        "title_score": title_score,
        "must_score": round(must_score),
        "nice_score": round(nice_score),
        "industry_score": industry_score,
        "location_score": loc_score,
        "reasons": reasons or ["No strong signals found"],
        "missing_keywords": missing,
        "strengths": strengths[:6],
        "pre_filtered": False,
    }


class MatchAgent:
    def __init__(self, preferences: dict):
        self.preferences = preferences
        self.min_score = preferences.get("min_match_score", 75)
        os.makedirs("output", exist_ok=True)
        self._resume = self._load_parsed_resume()
        self._model = SentenceTransformer("jjzha/jobbert-base-cased")
        self._candidate_query = self._build_candidate_query()
        self._candidate_embedding = self._model.encode(self._candidate_query)

    def _load_parsed_resume(self) -> dict:
        path = Path("data/parsed_resume.json")
        if not path.exists():
            raise FileNotFoundError(
                "data/parsed_resume.json not found. "
                "Run utils/resume_parser.py to generate it first."
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def _build_candidate_query(self) -> str:
        r = self._resume
        skills = ", ".join(r.get("skills", []))
        years = r.get("years", "?")
        level = r.get("level", "")
        industries = ", ".join(r.get("industries", []))
        roles = ", ".join(r.get("roles", []))
        return (
            f"Skills: {skills}\n"
            f"Experience: {years} years, {level}\n"
            f"Industries: {industries}\n"
            f"Role targets: {roles}"
        )

    def run(self, jobs: list) -> list:
        console.print(f"[dim][Match] Scoring {len(jobs)} jobs...[/dim]")

        if not jobs:
            self._print_scores([])
            return []

        # ── Stage 1: BM25 recall ─────────────────────────────────────────
        query_tokens = _build_bm25_query_tokens(self.preferences)
        corpus = [
            _norm(job.get("title", "") + " " + job.get("description", "")).split()
            for job in jobs
        ]
        bm25 = BM25Okapi(corpus)
        raw_bm25_scores = list(bm25.get_scores(query_tokens))

        bm25_threshold = min(150, len(jobs))
        sorted_indices = sorted(
            range(len(jobs)), key=lambda i: raw_bm25_scores[i], reverse=True
        )
        top_list = sorted_indices[:bm25_threshold]
        top_indices = set(top_list)

        top_raw_bm25 = [raw_bm25_scores[i] for i in top_list]
        top_bm25_normalized = _minmax_normalize(top_raw_bm25, 0.0, 30.0)
        top_bm25_map = {
            top_list[pos]: top_bm25_normalized[pos] for pos in range(len(top_list))
        }

        # ── Stage 2: JobBERT Bi-Encoder rerank on top 150 ────────────────
        top_jobs = [jobs[i] for i in top_list]
        passages = [
            f"Job Title: {job.get('title', '')}\n"
            f"Job Description: {job.get('description', '')[:1500]}"
            for job in top_jobs
        ]
        job_embeddings = self._model.encode(passages, batch_size=32)
        raw_jobbert_scores = list(
            util.cos_sim(self._candidate_embedding, job_embeddings)[0]
        )
        jobbert_normalized = _minmax_normalize(raw_jobbert_scores, 0.0, 40.0)
        jobbert_map = {
            top_list[pos]: jobbert_normalized[pos] for pos in range(len(top_list))
        }

        # ── Score all jobs ────────────────────────────────────────────────
        _below = {
            "score": 0,
            "bm25_score": 0,
            "jobbert_score": 0,
            "title_score": 0,
            "industry_score": 0,
            "location_score": 0,
            "reasons": ["below BM25 recall threshold"],
            "missing_keywords": [],
            "strengths": [],
        }

        qualifying = []

        for idx, job in enumerate(jobs):
            title = job.get("title", "?")
            company = job.get("company", "?")

            if idx not in top_indices:
                job["match_analysis"] = {**_below}
                console.print(
                    f"  [dim]✗ {title} @ {company} (below BM25 threshold)[/dim]"
                )
                continue

            scored = _score_job(job, self.preferences)

            if scored.get("pre_filtered"):
                bm25_s = round(top_bm25_map[idx])
                job["match_analysis"] = {
                    "score": 0,
                    "bm25_score": bm25_s,
                    "jobbert_score": 0,
                    "title_score": 0,
                    "industry_score": 0,
                    "location_score": 0,
                    "reasons": scored["reasons"],
                    "missing_keywords": scored.get("missing_keywords", []),
                    "strengths": scored.get("strengths", []),
                }
                console.print(
                    f"  [dim]✗ {title} @ {company} (filtered: {scored['reasons'][0]})[/dim]"
                )
                continue

            bm25_s = round(top_bm25_map[idx])
            jobbert_s = round(float(jobbert_map[idx]))
            title_s = round(scored["title_score"] / 2.5)
            industry_s = scored["industry_score"]
            location_s = scored["location_score"]

            total = bm25_s + jobbert_s + title_s + industry_s + location_s
            final_score = min(100, total)

            job["match_analysis"] = {
                "score": final_score,
                "bm25_score": bm25_s,
                "jobbert_score": jobbert_s,
                "title_score": title_s,
                "industry_score": industry_s,
                "location_score": location_s,
                "reasons": scored["reasons"],
                "missing_keywords": scored["missing_keywords"],
                "strengths": scored["strengths"],
            }

            if final_score >= self.min_score:
                qualifying.append(job)
                console.print(
                    f"  [green]✓ {title} @ {company} (score {final_score})[/green]"
                )
            else:
                console.print(
                    f"  [dim]✗ {title} @ {company} (score {final_score})[/dim]"
                )

        qualifying.sort(key=lambda j: j["match_analysis"].get("score", 0), reverse=True)
        self._print_scores(qualifying)
        return qualifying

    def _print_scores(self, jobs: list):
        table = Table(title=f"Qualifying Jobs (score ≥ {self.min_score})")
        table.add_column("Score", style="bold green", justify="right")
        table.add_column("Title")
        table.add_column("Company", style="magenta")
        table.add_column("Strengths")
        for job in jobs:
            analysis = job.get("match_analysis", {})
            strengths = ", ".join(analysis.get("strengths", [])[:3])
            table.add_row(
                str(analysis.get("score", 0)),
                job.get("title", ""),
                job.get("company", ""),
                strengths,
            )
        console.print(table)
