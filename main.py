import argparse
import json
from datetime import date

import yaml
from rich.console import Console
from rich.panel import Panel

import config as cfg
from agents.match_agent import MatchAgent
from agents.search_agent import search_jobs
from api.database import db_session, init_db
from api.services import job_service, run_service
from utils.job_cache import JobCache

console = Console()


def load_preferences(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("preferences", data)


_MOCK_JOB = {
    "title": "Backend Engineer",
    "company": "Razorpay",
    "location": "Remote",
    "description": (
        "We're looking for a Backend Engineer to join our Payments Platform team. "
        "You'll design and build high-throughput REST API services in Python using FastAPI, "
        "work with PostgreSQL and Redis, and deploy microservices on AWS with Docker and Kubernetes. "
        "Experience with Backend development, REST API design, and distributed systems is required."
    ),
    "url": "https://razorpay.com/jobs/backend-engineer-payments-platform/",
    "apply_url": "https://razorpay.com/jobs/backend-engineer-payments-platform/",
    "salary": "₹30–45 LPA",
    "date_posted": date.today().isoformat(),
    "source": "mock",
    "platform": "mock",
}


def run(prefs_path: str, refresh: bool = False, mock: bool = False):
    prefs = load_preferences(prefs_path)

    yaml_pi = prefs.get("personal_info", {})
    if yaml_pi:
        name = yaml_pi.get("name", "")
        cfg.PERSONAL_INFO.update(
            {
                "first_name": name.split()[0]
                if name
                else cfg.PERSONAL_INFO["first_name"],
                "last_name": " ".join(name.split()[1:])
                if name
                else cfg.PERSONAL_INFO["last_name"],
                "email": yaml_pi.get("email", cfg.PERSONAL_INFO["email"]),
                "phone": yaml_pi.get("phone", cfg.PERSONAL_INFO["phone"]),
                "linkedin_url": yaml_pi.get(
                    "linkedin", cfg.PERSONAL_INFO["linkedin_url"]
                ),
                "github_url": yaml_pi.get("github", cfg.PERSONAL_INFO["github_url"]),
                "portfolio_url": yaml_pi.get(
                    "portfolio", cfg.PERSONAL_INFO["portfolio_url"]
                ),
            }
        )

    console.print(
        Panel("[bold green]Job Agent[/bold green]  |  Search & Score", expand=False)
    )

    init_db()

    # Create run record — finished_at stays null if pipeline crashes
    with db_session() as session:
        current_run = run_service.create_run(session, json.dumps(prefs, default=str))
        run_id = current_run.id

    # Step 1 — Search
    console.rule("[bold]Step 1 · Search[/bold]")

    if mock:
        console.print("[dim]Mock mode — using 1 fake job, skipping scrape.[/dim]")
        all_jobs = [_MOCK_JOB]
    else:
        hours_old = prefs.get("search", {}).get("hours_old", 72)
        cache = JobCache(ttl_hours=hours_old)

        if refresh or cache.is_empty():
            reason = "--refresh" if refresh else "cache empty"
            console.print(f"[dim]Scraping fresh jobs ({reason})...[/dim]")
            fresh_jobs = search_jobs(prefs_path)
            added = cache.merge(fresh_jobs)
            console.print(f"[green]{added} new jobs cached.[/green]")
        else:
            console.print(f"[green]Using {len(cache)} cached job(s).[/green]")

        all_jobs = cache.all_jobs()
        if not all_jobs:
            console.print("[yellow]No jobs found. Try --refresh.[/yellow]")
            return

    # Step 2 — Score and filter
    console.rule("[bold]Step 2 · Match & Score[/bold]")
    match_agent = MatchAgent(prefs)
    qualifying = match_agent.run(all_jobs)

    rejected_count = len(all_jobs) - len(qualifying)

    source_counts: dict[str, int] = {}
    for job in all_jobs:
        src = job.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
    breakdown = ", ".join(f"{src}: {n}" for src, n in sorted(source_counts.items()))

    console.print(
        f"\n[bold]{len(all_jobs)} scraped ({breakdown})[/bold]\n"
        f"[bold green]{len(qualifying)} to apply → [/bold green]"
        f"[dim]{rejected_count} rejected[/dim]"
    )

    # Step 3 — Persist qualifying jobs and close the run
    console.rule("[bold]Step 3 · Persist[/bold]")
    with db_session() as session:
        for job in qualifying:
            job_service.upsert_job(session, job, run_id)
        run_service.finish_run(
            session, run_id, len(all_jobs), len(qualifying), rejected_count
        )

    console.print(
        f"[bold green]{len(qualifying)} jobs written to output/jobs.db[/bold green]"
    )
    console.print("[dim]Start the API with: just api[/dim]")


def main():
    parser = argparse.ArgumentParser(
        description="Job Agent — search, score, persist to DB"
    )
    parser.add_argument(
        "--prefs", default="data/preferences.yaml", help="Preferences YAML"
    )
    parser.add_argument(
        "--refresh", action="store_true", help="Force re-scrape, ignore cache"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use one fake job to test the pipeline end-to-end",
    )
    args = parser.parse_args()
    run(prefs_path=args.prefs, refresh=args.refresh, mock=args.mock)


if __name__ == "__main__":
    main()
