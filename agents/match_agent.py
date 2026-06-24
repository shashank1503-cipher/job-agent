import csv
import os
import re

from rich.console import Console
from rich.table import Table

console = Console()


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", text.lower())


def _hits(text_norm: str, keywords: list) -> list:
    return [kw for kw in keywords if _norm(kw) in text_norm]


def _score_job(job: dict, prefs: dict) -> dict:
    title = job.get("title", "")
    company = job.get("company", "")
    location = job.get("location", "")
    description = job.get("description", "")

    title_norm = _norm(title)
    company_norm = company.lower().strip()
    loc_norm = _norm(location)
    full_norm = _norm(f"{title} {description}")
    # Only scan the top of the description for hard-exclude keywords so we
    # don't reject jobs that merely mention an excluded tech in passing.
    head_norm = _norm(f"{title} {description[:400]}")

    # ── Hard disqualifiers ────────────────────────────────────────────────
    exclude_companies = {c.lower() for c in prefs.get("exclude_companies", [])}
    if company_norm in exclude_companies:
        return {
            "score": 0,
            "reasons": [f"Excluded company: {company}"],
            "missing_keywords": [],
            "strengths": [],
        }

    for kw in prefs.get("keywords_exclude", []):
        if _norm(kw) in head_norm:
            return {
                "score": 0,
                "reasons": [f"Excluded keyword in posting: {kw}"],
                "missing_keywords": [],
                "strengths": [],
            }

    # ── Remote location filter ─────────────────────────────────────────────
    # If remote_locations is set, remote jobs that specify a non-matching
    # country/region are hard-rejected. Plain "Remote" with no country passes.
    remote_locations = prefs.get("remote_locations", [])
    if remote_locations and "remote" in loc_norm:
        loc_without_remote = loc_norm.replace("remote", "").strip(" ,·-–")
        if loc_without_remote:  # there's a country/region specified
            allowed = [_norm(r) for r in remote_locations]
            if not any(r in loc_norm for r in allowed):
                return {
                    "score": 0,
                    "reasons": [f"Remote job outside allowed region: {location}"],
                    "missing_keywords": [],
                    "strengths": [],
                }

    # ── Title match (0–35) ────────────────────────────────────────────────
    title_score = 0
    for role in prefs.get("roles", []):
        role_words = _norm(role).split()
        if all(w in title_norm for w in role_words):
            title_score = 35
            break
        meaningful = [w for w in role_words if len(w) > 3]
        if meaningful and any(w in title_norm for w in meaningful):
            title_score = max(title_score, 15)

    # ── Must-have keywords (0–40) ─────────────────────────────────────────
    must_have = prefs.get("keywords_must_have", [])
    must_hits = _hits(full_norm, must_have)
    must_score = (len(must_hits) / len(must_have) * 40) if must_have else 40

    # ── Nice-to-have keywords (0–15) ──────────────────────────────────────
    nice_to_have = prefs.get("keywords_nice_to_have", [])
    nice_hits = _hits(full_norm, nice_to_have)
    nice_score = (len(nice_hits) / len(nice_to_have) * 15) if nice_to_have else 0

    # ── Location match (0–10) ─────────────────────────────────────────────
    loc_score = 0
    if "remote" in loc_norm:
        loc_score = 10
    else:
        for dloc in prefs.get("locations", []):
            if _norm(dloc) in loc_norm or loc_norm in _norm(dloc):
                loc_score = 10
                break

    total = round(title_score + must_score + nice_score + loc_score)
    score = min(100, total)

    # ── Human-readable output ─────────────────────────────────────────────
    reasons = []
    if title_score >= 35:
        reasons.append(f"Strong title match")
    elif title_score > 0:
        reasons.append(f"Partial title match")
    if must_have:
        reasons.append(f"{len(must_hits)}/{len(must_have)} must-have keywords matched")
    if nice_hits:
        reasons.append(f"{len(nice_hits)} nice-to-have keywords found")
    if loc_score:
        reasons.append(f"Location OK ({location})")

    missing = [kw for kw in must_have if kw not in must_hits]
    strengths = must_hits + [kw for kw in nice_hits if kw not in must_hits]

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
