import logging
import time

import httpx
from bs4 import BeautifulSoup

from utils.text_utils import _clean

logger = logging.getLogger(__name__)

_BASE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
_RATE_SLEEP = 0.2


def fetch_greenhouse_jobs(slugs: list[str], keywords: list[str]) -> list[dict]:
    """Fetch jobs from Greenhouse public board API for each slug.

    Filters by any of the given keywords appearing in the title or content.
    Returns a list of normalized job dicts.
    """
    lower_keywords = [kw.lower() for kw in keywords]
    results: list[dict] = []

    for slug in slugs:
        url = _BASE.format(slug=slug)
        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            if resp.status_code != 200:
                logger.debug(
                    "Greenhouse %s → HTTP %d, skipping.", slug, resp.status_code
                )
                time.sleep(_RATE_SLEEP)
                continue
            data = resp.json()
        except Exception as e:
            logger.debug("Greenhouse %s → error: %s, skipping.", slug, e)
            time.sleep(_RATE_SLEEP)
            continue

        jobs = data.get("jobs") or []
        if not jobs:
            time.sleep(_RATE_SLEEP)
            continue

        for job in jobs:
            title = job.get("title", "") or ""
            content_html = job.get("content", "") or ""
            content_text = _clean(BeautifulSoup(content_html, "html.parser").get_text())

            # Keyword filter
            combined = (title + " " + content_text).lower()
            if not any(kw in combined for kw in lower_keywords):
                continue

            # Company name from metadata if available
            company_name = slug
            meta = job.get("metadata") or []
            for m in meta:
                if isinstance(m, dict) and m.get("name", "").lower() == "company":
                    company_name = m.get("value", slug) or slug
                    break

            location_obj = job.get("location") or {}
            results.append(
                {
                    "title": title,
                    "company": company_name,
                    "location": location_obj.get("name", "")
                    if isinstance(location_obj, dict)
                    else "",
                    "description": content_text,
                    "url": job.get("absolute_url", "") or "",
                    "salary": "",
                    "date_posted": job.get("updated_at", "") or "",
                    "source": "greenhouse",
                }
            )

        time.sleep(_RATE_SLEEP)

    return results
