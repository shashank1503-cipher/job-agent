import argparse
import csv
import html as html_lib
import os
from datetime import date

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import config as cfg
from agents.match_agent import MatchAgent
from agents.search_agent import search_jobs
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
    os.makedirs("output", exist_ok=True)

    prefs = load_preferences(prefs_path)

    yaml_pi = prefs.get("personal_info", {})
    if yaml_pi:
        name = yaml_pi.get("name", "")
        cfg.PERSONAL_INFO.update({
            "first_name": name.split()[0] if name else cfg.PERSONAL_INFO["first_name"],
            "last_name": " ".join(name.split()[1:]) if name else cfg.PERSONAL_INFO["last_name"],
            "email": yaml_pi.get("email", cfg.PERSONAL_INFO["email"]),
            "phone": yaml_pi.get("phone", cfg.PERSONAL_INFO["phone"]),
            "linkedin_url": yaml_pi.get("linkedin", cfg.PERSONAL_INFO["linkedin_url"]),
            "github_url": yaml_pi.get("github", cfg.PERSONAL_INFO["github_url"]),
            "portfolio_url": yaml_pi.get("portfolio", cfg.PERSONAL_INFO["portfolio_url"]),
        })

    console.print(Panel("[bold green]Job Agent[/bold green]  |  Search & Score", expand=False))

    # Step 1 — Search (mock / cache-first / live scrape)
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

    qualifying_urls = {j.get("url") for j in qualifying}
    rejected = [j for j in all_jobs if j.get("url") not in qualifying_urls]
    rejected_count = len(rejected)

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

    # Step 3 — Write apply list
    console.rule("[bold]Step 3 · Output[/bold]")
    _write_apply_list(qualifying)
    _write_html_report(qualifying, len(all_jobs))
    _write_rejected(rejected)
    _write_rejected_html(rejected, len(all_jobs))

    console.print(f"[bold green]→ output/apply_list.html[/bold green]  (open in browser, click Apply)")
    console.print(f"[dim]→ output/rejected_jobs.html  ·  output/apply_list.csv  ·  output/rejected_jobs.csv[/dim]")


def _write_apply_list(jobs: list):
    path = "output/apply_list.csv"
    fields = ["rank", "score", "title", "company", "location", "url", "salary", "date_posted", "source", "strengths", "missing"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i, job in enumerate(jobs, 1):
            analysis = job.get("match_analysis", {})
            writer.writerow({
                "rank": i,
                "score": analysis.get("score", ""),
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "location": job.get("location", ""),
                "url": job.get("url", ""),
                "salary": job.get("salary", ""),
                "date_posted": job.get("date_posted", ""),
                "source": job.get("source", ""),
                "strengths": ", ".join(analysis.get("strengths", [])),
                "missing": ", ".join(analysis.get("missing_keywords", [])),
            })


def _write_html_report(qualifying: list, total_scraped: int):
    today = date.today().strftime("%d %b %Y")
    e = html_lib.escape

    cards = []
    for i, job in enumerate(qualifying, 1):
        analysis = job.get("match_analysis", {})
        score = analysis.get("score", 0)
        score_cls = "s-high" if score >= 80 else ("s-mid" if score >= 60 else "s-low")

        strengths = analysis.get("strengths", [])
        missing = analysis.get("missing_keywords", [])
        meta_parts = [p for p in [job.get("location", ""), job.get("source", ""), job.get("date_posted", "")] if p]
        salary = job.get("salary", "")

        chips = "".join(f'<span class="chip cm">{e(s)}</span>' for s in strengths)
        chips += "".join(f'<span class="chip cx">{e(m)}</span>' for m in missing)

        cards.append(f"""
  <article class="card">
    <span class="rank">#{i}</span>
    <span class="score {score_cls}">{score}</span>
    <div class="body">
      <div class="title-row">
        <span class="title">{e(job.get('title',''))}</span>
        <span class="company">{e(job.get('company',''))}</span>
      </div>
      <div class="meta">{e(' · '.join(meta_parts))}{f'  <span class="salary">{e(salary)}</span>' if salary else ''}</div>
      {f'<div class="chips">{chips}</div>' if chips else ''}
    </div>
    <a href="{e(job.get('url','#'))}" target="_blank" rel="noopener" class="apply-btn">Apply →</a>
  </article>""")

    body = "\n".join(cards) if cards else '<p class="empty">No matching jobs found.</p>'

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Apply List · {today}</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --bg:      #f5f4f1;
  --surface: #ffffff;
  --border:  #e3e1db;
  --text:    #18181a;
  --muted:   #77756e;
  --blue:    #1a5cdb;
  --blue-dk: #1448b8;
  --s-high-bg:  #d4f4e2; --s-high-tx: #165c35;
  --s-mid-bg:   #fef0cc; --s-mid-tx:  #7a4e00;
  --s-low-bg:   #fde0e0; --s-low-tx:  #8a1f1f;
  --cm-bg:   #e8f0fe; --cm-tx: #1a4ab8;
  --cx-bg:   #f3f3f3; --cx-tx: #888;
  font-size: 15px;
}}
body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; line-height: 1.5; }}
header {{ max-width: 900px; margin: 0 auto; padding: 2.5rem 1.5rem 1.5rem; border-bottom: 1px solid var(--border); }}
header h1 {{ font-size: 1.25rem; font-weight: 700; letter-spacing: -.01em; }}
.sub {{ font-size: 0.8rem; color: var(--muted); margin-top: .2rem; }}
main {{ max-width: 900px; margin: 0 auto; padding: 0 1.5rem 4rem; }}
.card {{
  display: grid;
  grid-template-columns: 2.2rem 3rem 1fr auto;
  gap: .75rem 1rem;
  align-items: center;
  padding: 1rem 0;
  border-bottom: 1px solid var(--border);
}}
.card:first-child {{ padding-top: 1.25rem; }}
.rank {{ font-size: .75rem; color: var(--muted); font-variant-numeric: tabular-nums; text-align: right; padding-top: .1rem; }}
.score {{
  font-size: .95rem; font-weight: 700; font-variant-numeric: tabular-nums;
  text-align: center; padding: .2rem .3rem; border-radius: 4px;
  line-height: 1.4;
}}
.s-high {{ background: var(--s-high-bg); color: var(--s-high-tx); }}
.s-mid  {{ background: var(--s-mid-bg);  color: var(--s-mid-tx);  }}
.s-low  {{ background: var(--s-low-bg);  color: var(--s-low-tx);  }}
.body {{ min-width: 0; }}
.title-row {{ display: flex; align-items: baseline; gap: .6rem; flex-wrap: wrap; }}
.title {{ font-weight: 600; font-size: .95rem; }}
.company {{ color: var(--muted); font-size: .85rem; }}
.meta {{ font-size: .78rem; color: var(--muted); margin-top: .18rem; }}
.salary {{ font-weight: 500; color: var(--text); }}
.chips {{ display: flex; flex-wrap: wrap; gap: .3rem; margin-top: .4rem; }}
.chip {{ font-size: .7rem; padding: .15rem .45rem; border-radius: 3px; white-space: nowrap; }}
.cm {{ background: var(--cm-bg); color: var(--cm-tx); }}
.cx {{ background: var(--cx-bg); color: var(--cx-tx); text-decoration: line-through; }}
.apply-btn {{
  display: inline-block; padding: .45rem .9rem;
  background: var(--blue); color: #fff;
  font-size: .82rem; font-weight: 600; text-decoration: none;
  border-radius: 5px; white-space: nowrap;
  transition: background .15s;
}}
.apply-btn:hover {{ background: var(--blue-dk); }}
.apply-btn:focus-visible {{ outline: 2px solid var(--blue); outline-offset: 2px; }}
.empty {{ padding: 3rem 0; text-align: center; color: var(--muted); }}
@media (max-width: 600px) {{
  .card {{ grid-template-columns: 2rem 2.8rem 1fr; }}
  .apply-btn {{ grid-column: 1 / -1; width: fit-content; margin-left: auto; }}
}}
</style>
</head>
<body>
<header>
  <h1>Apply List</h1>
  <p class="sub">{today} &nbsp;·&nbsp; {len(qualifying)} matched &nbsp;·&nbsp; {total_scraped} scraped</p>
</header>
<main>
{body}
</main>
</body>
</html>"""

    with open("output/apply_list.html", "w", encoding="utf-8") as f:
        f.write(html)


def _write_rejected(rejected: list):
    path = "output/rejected_jobs.csv"
    fields = ["score", "title", "company", "location", "url", "source", "reasons"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for job in rejected:
            analysis = job.get("match_analysis", {})
            writer.writerow({
                "score": analysis.get("score", ""),
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "location": job.get("location", ""),
                "url": job.get("url", ""),
                "source": job.get("source", ""),
                "reasons": "; ".join(analysis.get("reasons", [])),
            })


def _write_rejected_html(rejected: list, total_scraped: int):
    today = date.today().strftime("%d %b %Y")
    e = html_lib.escape

    cards = []
    for i, job in enumerate(rejected, 1):
        analysis = job.get("match_analysis", {})
        score = analysis.get("score", 0)
        score_cls = "s-high" if score >= 80 else ("s-mid" if score >= 60 else "s-low")

        strengths = analysis.get("strengths", [])
        missing = analysis.get("missing_keywords", [])
        reasons = "; ".join(analysis.get("reasons", []))
        meta_parts = [p for p in [job.get("location", ""), job.get("source", ""), job.get("date_posted", "")] if p]

        chips = "".join(f'<span class="chip cm">{e(s)}</span>' for s in strengths)
        chips += "".join(f'<span class="chip cx">{e(m)}</span>' for m in missing)

        cards.append(f"""
  <article class="card">
    <span class="rank">#{i}</span>
    <span class="score {score_cls}">{score}</span>
    <div class="body">
      <div class="title-row">
        <span class="title">{e(job.get('title', ''))}</span>
        <span class="company">{e(job.get('company', ''))}</span>
      </div>
      <div class="meta">{e(' · '.join(meta_parts))}</div>
      {f'<div class="reason">{e(reasons)}</div>' if reasons else ''}
      {f'<div class="chips">{chips}</div>' if chips else ''}
    </div>
  </article>""")

    body = "\n".join(cards) if cards else '<p class="empty">No rejected jobs.</p>'

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rejected Jobs · {today}</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --bg:      #f5f4f1;
  --surface: #ffffff;
  --border:  #e3e1db;
  --text:    #18181a;
  --muted:   #77756e;
  --s-high-bg:  #d4f4e2; --s-high-tx: #165c35;
  --s-mid-bg:   #fef0cc; --s-mid-tx:  #7a4e00;
  --s-low-bg:   #fde0e0; --s-low-tx:  #8a1f1f;
  --cm-bg:   #e8f0fe; --cm-tx: #1a4ab8;
  --cx-bg:   #f3f3f3; --cx-tx: #888;
  --reason-tx: #a0302a;
  font-size: 15px;
}}
body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; line-height: 1.5; }}
header {{ max-width: 900px; margin: 0 auto; padding: 2.5rem 1.5rem 1.5rem; border-bottom: 1px solid var(--border); }}
header h1 {{ font-size: 1.25rem; font-weight: 700; letter-spacing: -.01em; }}
.sub {{ font-size: 0.8rem; color: var(--muted); margin-top: .2rem; }}
main {{ max-width: 900px; margin: 0 auto; padding: 0 1.5rem 4rem; }}
.card {{
  display: grid;
  grid-template-columns: 2.2rem 3rem 1fr;
  gap: .75rem 1rem;
  align-items: center;
  padding: 1rem 0;
  border-bottom: 1px solid var(--border);
}}
.card:first-child {{ padding-top: 1.25rem; }}
.rank {{ font-size: .75rem; color: var(--muted); font-variant-numeric: tabular-nums; text-align: right; padding-top: .1rem; }}
.score {{
  font-size: .95rem; font-weight: 700; font-variant-numeric: tabular-nums;
  text-align: center; padding: .2rem .3rem; border-radius: 4px;
  line-height: 1.4;
}}
.s-high {{ background: var(--s-high-bg); color: var(--s-high-tx); }}
.s-mid  {{ background: var(--s-mid-bg);  color: var(--s-mid-tx);  }}
.s-low  {{ background: var(--s-low-bg);  color: var(--s-low-tx);  }}
.body {{ min-width: 0; }}
.title-row {{ display: flex; align-items: baseline; gap: .6rem; flex-wrap: wrap; }}
.title {{ font-weight: 600; font-size: .95rem; }}
.company {{ color: var(--muted); font-size: .85rem; }}
.meta {{ font-size: .78rem; color: var(--muted); margin-top: .18rem; }}
.reason {{ font-size: .78rem; color: var(--reason-tx); margin-top: .18rem; }}
.chips {{ display: flex; flex-wrap: wrap; gap: .3rem; margin-top: .4rem; }}
.chip {{ font-size: .7rem; padding: .15rem .45rem; border-radius: 3px; white-space: nowrap; }}
.cm {{ background: var(--cm-bg); color: var(--cm-tx); }}
.cx {{ background: var(--cx-bg); color: var(--cx-tx); text-decoration: line-through; }}
.empty {{ padding: 3rem 0; text-align: center; color: var(--muted); }}
@media (max-width: 600px) {{
  .card {{ grid-template-columns: 2rem 2.8rem 1fr; }}
}}
</style>
</head>
<body>
<header>
  <h1>Rejected Jobs</h1>
  <p class="sub">{today} &nbsp;·&nbsp; {len(rejected)} rejected &nbsp;·&nbsp; {total_scraped} scraped</p>
</header>
<main>
{body}
</main>
</body>
</html>"""

    with open("output/rejected_jobs.html", "w", encoding="utf-8") as f:
        f.write(html)


def main():
    parser = argparse.ArgumentParser(description="Job Agent — search, score, output apply list")
    parser.add_argument("--prefs", default="data/preferences.yaml", help="Preferences YAML")
    parser.add_argument("--refresh", action="store_true", help="Force re-scrape, ignore cache")
    parser.add_argument("--mock", action="store_true", help="Use one fake job to test the pipeline end-to-end")
    args = parser.parse_args()
    run(prefs_path=args.prefs, refresh=args.refresh, mock=args.mock)


if __name__ == "__main__":
    main()
