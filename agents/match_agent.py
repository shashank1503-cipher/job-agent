import csv
import os
import re

from rich.console import Console
from rich.table import Table

console = Console()

# Matches experience requirements like "8+ years", "10+ years", "minimum 8 years"
_EXP_GATE = re.compile(
    r'\b(8|9|10|11|12|15)\+\s*years?\b'
    r'|\bminimum\s+(?:of\s+)?(8|9|10|11|12|15)\s*years?\b',
    re.IGNORECASE,
)

_NO_REMOTE = re.compile(r'\bnot?\s+remote\b', re.IGNORECASE)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", text.lower())


def _hits(text_norm: str, keywords: list) -> list:
    return [kw for kw in keywords if _norm(kw) in text_norm]


def _parse_salary_lpa(salary_str: str) -> float | None:
    if not salary_str:
        return None
    s = salary_str.lower()
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:lpa|l\.p\.a|lakh)', s)
    if m:
        return float(m.group(1))
    m = re.search(r'(\d+(?:\.\d+)?)', s)
    if m:
        val = float(m.group(1))
        if 5 <= val <= 200:
            return val
    return None


def _score_job(job: dict, prefs: dict) -> dict:
    title = job.get("title", "")
    company = job.get("company", "")
    location = job.get("location", "")
    description = job.get("description", "")

    title_norm = _norm(title)
    company_norm = company.lower().strip()
    loc_norm = _norm(location)
    full_norm = _norm(f"{title} {description}")
    head_norm = _norm(f"{title} {description[:500]}")

    # ── Hard disqualifiers ────────────────────────────────────────────────
    exclude_companies = {c.lower() for c in prefs.get("exclude_companies", [])}
    if company_norm in exclude_companies:
        return {"score": 0, "reasons": [f"Excluded company: {company}"], "missing_keywords": [], "strengths": []}

    for kw in prefs.get("keywords_exclude", []):
        if _norm(kw) in head_norm:
            return {"score": 0, "reasons": [f"Excluded keyword in posting: {kw}"], "missing_keywords": [], "strengths": []}

    max_exp = prefs.get("experience_years", {}).get("max", 99)
    if max_exp <= 4:
        m = _EXP_GATE.search(description[:600])
        if m:
            return {"score": 0, "reasons": [f"Requires {m.group(0).strip()} experience"], "missing_keywords": [], "strengths": []}

    min_salary = prefs.get("min_salary_lpa")
    if min_salary:
        salary_lpa = _parse_salary_lpa(job.get("salary", ""))
        if salary_lpa is not None and salary_lpa < min_salary:
            return {"score": 0, "reasons": [f"Salary {salary_lpa} LPA below minimum {min_salary} LPA"], "missing_keywords": [], "strengths": []}

    remote_locations = prefs.get("remote_locations", [])
    if remote_locations and "remote" in loc_norm:
        loc_without_remote = loc_norm.replace("remote", "").strip()
        if loc_without_remote:
            loc_words = set(loc_without_remote.split())
            def _region_match(region):
                if len(region) <= 3:
                    return bool(re.search(r'\b' + re.escape(region) + r'\b', location))
                return _norm(region) in loc_words
            if not any(_region_match(r) for r in remote_locations):
                return {"score": 0, "reasons": [f"Remote job outside allowed region: {location}"], "missing_keywords": [], "strengths": []}

    # ── Title match (0–25) ────────────────────────────────────────────────
    title_score = 0
    for role in prefs.get("roles", []):
        role_words = _norm(role).split()
        if all(w in title_norm for w in role_words):
            title_score = 25
            break
        meaningful = [w for w in role_words if len(w) > 3]
        if meaningful and any(w in title_norm for w in meaningful):
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

    # ── Location match (0–10) ─────────────────────────────────────────────
    loc_score = 0
    if "remote" in loc_norm and not _NO_REMOTE.search(location):
        loc_score = 10
    elif "hybrid" in loc_norm:
        for dloc in prefs.get("locations", []):
            dloc_norm = _norm(dloc)
            if dloc_norm != "remote" and (dloc_norm in loc_norm or loc_norm in dloc_norm):
                loc_score = 10
                break
    else:
        for dloc in prefs.get("locations", []):
            dloc_norm = _norm(dloc)
            if dloc_norm != "remote" and (dloc_norm in loc_norm or loc_norm in dloc_norm):
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
        "reasons": reasons or ["No strong signals found"],
        "missing_keywords": missing,
        "strengths": strengths[:6],
    }


class MatchAgent:
    def __init__(self, preferences: dict):
        self.preferences = preferences
        self.min_score = preferences.get("min_match_score", 75)
        os.makedirs("output", exist_ok=True)

    def run(self, jobs: list) -> list:
        qualifying = []
        rejected = []

        console.print(f"[dim][Match] Scoring {len(jobs)} jobs...[/dim]")
        for job in jobs:
            title = job.get("title", "?")
            company = job.get("company", "?")

            analysis = _score_job(job, self.preferences)
            job["match_analysis"] = analysis
            score = analysis.get("score", 0)

            if score >= self.min_score:
                qualifying.append(job)
                console.print(f"  [green]✓ {title} @ {company} (score {score})[/green]")
            else:
                rejected.append(job)
                console.print(f"  [dim]✗ {title} @ {company} (score {score})[/dim]")

        self._save_rejected(rejected)
        qualifying.sort(key=lambda j: j["match_analysis"].get("score", 0), reverse=True)
        self._print_scores(qualifying)
        return qualifying

    def _save_rejected(self, rejected: list):
        path = "output/rejected_jobs.csv"
        fieldnames = ["title", "company", "platform", "apply_url", "score", "reasons"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for job in rejected:
                analysis = job.get("match_analysis", {})
                writer.writerow({
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "platform": job.get("platform", ""),
                    "apply_url": job.get("apply_url", ""),
                    "score": analysis.get("score", 0),
                    "reasons": "; ".join(analysis.get("reasons", [])),
                })

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
