import logging
import time

import httpx
from bs4 import BeautifulSoup

from utils.text_utils import _clean

logger = logging.getLogger(__name__)

_BASE = "https://api.lever.co/v0/postings/{slug}?mode=json"
_RATE_SLEEP = 0.2


def fetch_lever_jobs(slugs: list[str], keywords: list[str]) -> list[dict]:
    """Fetch jobs from Lever public postings API for each slug.

    Filters by any keyword appearing in the posting text or team category.
    Returns a list of normalized job dicts.
    """
    lower_keywords = [kw.lower() for kw in keywords]
    results: list[dict] = []

    for slug in slugs:
        url = _BASE.format(slug=slug)
        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            if resp.status_code != 200:
                logger.debug("Lever %s → HTTP %d, skipping.", slug, resp.status_code)
                time.sleep(_RATE_SLEEP)
                continue
            postings = resp.json()
        except Exception as e:
            logger.debug("Lever %s → error: %s, skipping.", slug, e)
            time.sleep(_RATE_SLEEP)
            continue

        if not postings:
            time.sleep(_RATE_SLEEP)
            continue

        for posting in postings:
            title = posting.get("text", "") or ""
            categories = posting.get("categories") or {}
            team = categories.get("team", "") or ""
            description_plain = posting.get("descriptionPlain", "") or ""
            description_text = _clean(
                BeautifulSoup(description_plain, "html.parser").get_text()
            )

            combined = (title + " " + team + " " + description_text).lower()
            if not any(kw in combined for kw in lower_keywords):
                continue

            results.append(
                {
                    "title": title,
                    "company": slug,
                    "location": categories.get("location", "") or "",
                    "description": description_text,
                    "url": posting.get("hostedUrl", "") or "",
                    "salary": "",
                    "date_posted": "",
                    "source": "lever",
                }
            )

        time.sleep(_RATE_SLEEP)

    return results
