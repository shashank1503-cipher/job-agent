import os
import re

from rich.console import Console

console = Console()


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", text.lower())


def select_resume(job: dict, variants: list[dict]) -> str | None:
    """Pick the best pre-made resume PDF for this job by keyword overlap.

    Each variant is a dict with:
        path: str       — path to the PDF file
        tags: list[str] — keywords this resume emphasises

    Returns the path of the best matching variant, or None if no variants
    are configured or none of the files exist.
    """
    if not variants:
        console.print("[yellow][Resume] No resume_variants configured in preferences.yaml.[/yellow]")
        return None

    job_text = _norm(f"{job.get('title', '')} {job.get('description', '')}")

    best_path: str | None = None
    best_score = -1
    best_label = ""

    for variant in variants:
        path = variant.get("path", "")
        tags = variant.get("tags", [])
        label = variant.get("label", os.path.basename(path))

        if not os.path.exists(path):
            console.print(f"[yellow][Resume] Variant not found, skipping: {path}[/yellow]")
            continue

        score = sum(1 for tag in tags if _norm(tag) in job_text)

        if score > best_score:
            best_score = score
            best_path = path
            best_label = label

    if best_path:
        console.print(
            f"  [cyan][Resume] Selected '{best_label}' "
            f"({best_score} tag match(es))[/cyan]"
        )
    else:
        console.print("[yellow][Resume] No valid resume variants found.[/yellow]")

    return best_path
