import json
import logging
import re
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_CACHE_PATH = Path("data/companies.json")
_SOURCE_URL = "https://raw.githubusercontent.com/sample-resume/awesome-easy-apply/main/README.md"


def load_companies(force_refresh: bool = False) -> dict:
    """Return {"greenhouse": [...], "lever": [...]} slug lists.

    Fetches the community-maintained list from GitHub on first run and caches
    to data/companies.json. Subsequent calls load from cache unless
    force_refresh=True.
    """
    if not force_refresh and _CACHE_PATH.exists():
        try:
            with open(_CACHE_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if "greenhouse" in data and "lever" in data:
                return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Cache read failed (%s); re-fetching.", e)

    try:
        resp = httpx.get(_SOURCE_URL, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        markdown = resp.text
    except Exception as e:
        if _CACHE_PATH.exists():
            logger.warning("Network fetch failed (%s); falling back to cache.", e)
            with open(_CACHE_PATH, encoding="utf-8") as f:
                return json.load(f)
        raise RuntimeError(
            f"Cannot fetch company list and no cache available: {e}"
        ) from e

    # Extract all markdown links: [Label](url)
    urls = re.findall(r"\[.*?\]\((https?://[^)]+)\)", markdown)

    greenhouse: list[str] = []
    lever: list[str] = []
    seen: set[str] = set()

    for url in urls:
        gh_match = re.search(r"boards\.greenhouse\.io/([^/?#\s]+)", url)
        if gh_match:
            slug = gh_match.group(1).rstrip("/")
            if slug not in seen:
                seen.add(slug)
                greenhouse.append(slug)

        lv_match = re.search(r"jobs\.lever\.co/([^/?#\s]+)", url)
        if lv_match:
            slug = lv_match.group(1).rstrip("/")
            if slug not in seen:
                seen.add(slug)
                lever.append(slug)

    result = {"greenhouse": greenhouse, "lever": lever}

    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    logger.info(
        "Company slugs fetched: %d greenhouse, %d lever",
        len(greenhouse),
        len(lever),
    )
    return result
