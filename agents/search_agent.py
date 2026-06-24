import logging

import yaml
from jobspy import scrape_jobs
from rich.console import Console

from platforms.greenhouse_client import fetch_greenhouse_jobs
from platforms.lever_client import fetch_lever_jobs
from utils.company_loader import load_companies

console = Console()
logger = logging.getLogger(__name__)

_TYPE_MAP = {
    "full-time": "fulltime",
    "part-time": "parttime",
    "contract": "contract",
    "internship": "internship",
}


def search_jobs(preferences_path: str = "data/preferences.yaml") -> list[dict]:
    """Search jobs from LinkedIn/Indeed (jobspy), Greenhouse, and Lever.

    Returns a deduplicated list of normalized job dicts, each with a
    non-empty description and url.
    """
    with open(preferences_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    prefs = data.get("preferences", data)

    roles: list[str] = prefs.get("roles", [])
    locations: list[str] = prefs.get("locations", [])

    employment_type_raw = prefs.get("employment_type", ["full-time"])
    raw_type = employment_type_raw[0] if employment_type_raw else "full-time"
    job_type = _TYPE_MAP.get(raw_type.lower(), "fulltime")

    search_cfg = prefs.get("search", {})
    sites: list[str] = search_cfg.get("sites", ["linkedin", "indeed"])
    results_per_role: int = search_cfg.get("results_per_role", 200)
    hours_old: int = search_cfg.get("hours_old", 72)
    country: str = search_cfg.get("country", "India")
    greenhouse_enabled: bool = search_cfg.get("greenhouse_enabled", True)
    lever_enabled: bool = search_cfg.get("lever_enabled", True)

    seen_urls: set[str] = set()
    all_jobs: list[dict] = []
    skipped_empty = 0

    # --- Source 1: jobspy (LinkedIn + Indeed) ---
    total_combos = len(roles) * len(locations)
    combo = 0
    for role in roles:
        for loc in locations:
            combo += 1
            is_remote = loc.lower() == "remote"
            # Append country to city names so LinkedIn respects the geography too;
            # for remote use the country itself as the location anchor.
            loc_param = country if is_remote else f"{loc}, {country}"
            console.print(
                f"[bold cyan][Search] ({combo}/{total_combos}) jobspy '{role}' @ '{loc_param}' on {sites}...[/bold cyan]"
            )
            try:
                df = scrape_jobs(
                    site_name=sites,
                    search_term=role,
                    location=loc_param,
                    is_remote=is_remote,
                    results_wanted=results_per_role,
                    hours_old=hours_old,
                    country_indeed=country,
                    job_type=job_type,
                    linkedin_fetch_description=True,
                )
                before = len(all_jobs)
                for _, row in df.iterrows():
                    url = str(row.get("job_url", "") or "").strip()
                    if not url or url in seen_urls:
                        continue
                    description = str(row.get("description", "") or "").strip()
                    if not description:
                        skipped_empty += 1
                        continue
                    seen_urls.add(url)
                    all_jobs.append({
                        "title": str(row.get("title", "") or ""),
                        "company": str(row.get("company", "") or ""),
                        "location": str(row.get("location", "") or ""),
                        "description": description,
                        "url": url,
                        "salary": str(row.get("min_amount", "") or ""),
                        "date_posted": str(row.get("date_posted", "") or ""),
                        "source": str(row.get("site", "") or ""),
                        "apply_url": url,
                        "platform": str(row.get("site", "") or ""),
                    })
                added = len(all_jobs) - before
                console.print(f"  [green]'{role}' @ '{loc}': {len(df)} scraped → {added} added[/green]")
            except Exception as e:
                console.print(f"[yellow][Search] Warning: jobspy '{role}' @ '{loc}' failed — {e}[/yellow]")

    # --- Source 2: Greenhouse ---
    if greenhouse_enabled:
        console.print("[bold cyan][Search] Fetching Greenhouse jobs...[/bold cyan]")
        try:
            companies = load_companies()
            gh_jobs = fetch_greenhouse_jobs(companies.get("greenhouse", []), keywords=roles)
            before = len(all_jobs)
            for job in gh_jobs:
                url = job.get("url", "").strip()
                if not url or url in seen_urls:
                    continue
                if not job.get("description", "").strip():
                    skipped_empty += 1
                    continue
                seen_urls.add(url)
                all_jobs.append({**job, "apply_url": url, "platform": "greenhouse"})
            console.print(f"  [green]Greenhouse: {len(gh_jobs)} fetched → {len(all_jobs) - before} added[/green]")
        except Exception as e:
            console.print(f"[yellow][Search] Warning: Greenhouse fetch failed — {e}[/yellow]")

    # --- Source 3: Lever ---
    if lever_enabled:
        console.print("[bold cyan][Search] Fetching Lever jobs...[/bold cyan]")
        try:
            # reuse companies dict if already fetched, otherwise load again
            if not greenhouse_enabled:
                companies = load_companies()
            lv_jobs = fetch_lever_jobs(companies.get("lever", []), keywords=roles)
            before = len(all_jobs)
            for job in lv_jobs:
                url = job.get("url", "").strip()
                if not url or url in seen_urls:
                    continue
                if not job.get("description", "").strip():
                    skipped_empty += 1
                    continue
                seen_urls.add(url)
                all_jobs.append({**job, "apply_url": url, "platform": "lever"})
            console.print(f"  [green]Lever: {len(lv_jobs)} fetched → {len(all_jobs) - before} added[/green]")
        except Exception as e:
            console.print(f"[yellow][Search] Warning: Lever fetch failed — {e}[/yellow]")

    if skipped_empty:
        console.print(f"[dim][Search] Skipped {skipped_empty} job(s) with empty descriptions.[/dim]")

    # Per-source breakdown
    source_counts: dict[str, int] = {}
    for job in all_jobs:
        src = job.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
    breakdown = ", ".join(f"{src}: {n}" for src, n in source_counts.items())
    console.print(
        f"[bold green]{len(all_jobs)} jobs found ({breakdown})[/bold green]"
    )

    return all_jobs


if __name__ == "__main__":
    jobs = search_jobs()
    print(f"Total jobs fetched: {len(jobs)}")
