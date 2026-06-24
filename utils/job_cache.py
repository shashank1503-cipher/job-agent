import json
import os
from datetime import datetime, timedelta, timezone

CACHE_PATH = "output/jobs_cache.json"
CACHE_TTL_HOURS = 72


class JobCache:
    """Persist scraped jobs to disk so scraping isn't repeated on every run.

    Jobs are keyed by apply_url. Entries older than ttl_hours are evicted
    automatically on load. Call remove() after a successful application so
    already-applied jobs don't clutter future runs.

    Set ttl_hours to match preferences.search.hours_old so the cache stays
    fresh for exactly as long as the scraped postings are relevant.
    """

    def __init__(self, path: str = CACHE_PATH, ttl_hours: int = CACHE_TTL_HOURS):
        self.path = path
        self.ttl_hours = ttl_hours
        self._data: dict = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding="utf-8") as f:
            self._data = json.load(f)
        self._evict_stale()

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, default=str)

    def _evict_stale(self):
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=self.ttl_hours)).isoformat()
        stale = [k for k, v in self._data.items() if v.get("cached_at", "") < cutoff]
        for k in stale:
            del self._data[k]
        if stale:
            self._save()

    def __len__(self) -> int:
        return len(self._data)

    def is_empty(self) -> bool:
        return len(self._data) == 0

    def merge(self, jobs: list[dict]) -> int:
        """Add new jobs to cache, skipping duplicates. Returns count added."""
        now = datetime.now(timezone.utc).isoformat()
        added = 0
        for job in jobs:
            key = job.get("apply_url") or job.get("url", "")
            if not key or key in self._data:
                continue
            # Store raw job data without match_analysis (re-scored each run)
            entry = {k: v for k, v in job.items() if k != "match_analysis"}
            entry["cached_at"] = now
            self._data[key] = entry
            added += 1
        if added:
            self._save()
        return added

    def remove(self, apply_url: str):
        """Remove a job from cache after it has been applied to."""
        if apply_url and apply_url in self._data:
            del self._data[apply_url]
            self._save()

    def all_jobs(self) -> list[dict]:
        return list(self._data.values())
