# Rejected Jobs HTML Page

**Date:** 2026-06-24
**Status:** Approved

## Goal

Expose rejected jobs (and why they were rejected) as a browsable HTML page served by the existing local web server, matching the style of `apply_list.html`.

## Scope

Two files changed, no new dependencies, no new framework:

- `main.py` — add `_write_rejected_html(rejected)` and call it in `run()`
- `serve.py` — print the second URL so the user knows it exists

## Data

`_write_rejected()` already computes the rejected list as jobs whose URL is not in `qualifying`. Each job has:

- `title`, `company`, `location`, `source`, `date_posted`
- `match_analysis.score` (int 0–100)
- `match_analysis.reasons` (list of strings, joined with `; ` in the CSV)
- `match_analysis.strengths` (matched keywords)
- `match_analysis.missing_keywords`

The HTML page reads this same list directly (not the CSV).

## HTML Page: `output/rejected_jobs.html`

### Layout

Identical card grid to `apply_list.html`:

```
rank | score | body (title, company, meta, chips, reason) | [no button]
```

### Score badge

Reuses `s-high / s-mid / s-low` colour classes:
- `s-high` (≥80): borderline rejections — useful to spot near-misses
- `s-mid` (60–79): partial matches
- `s-low` (<60): hard disqualifications (excluded keyword/company, low score)

### Rejection reason line

Each card shows a `reasons` line below the meta line, styled in muted red (`#c0392b` at reduced opacity). This is the primary new element — the reason the job was filtered out (e.g. "Excluded keyword in posting: .NET", "0/3 must-have keywords matched").

### Chips

Same green `cm` chips for matched keywords, strikethrough `cx` chips for missing keywords.

### No Apply button

Rejected jobs have no apply action. The fourth grid column is omitted for this page.

### Header

```
Rejected Jobs
24 Jun 2026  ·  3342 rejected  ·  3542 scraped
```

## `serve.py` Change

After the existing `print(f"Serving at {url} ...")` line, add:

```python
print(f"          → http://localhost:{PORT}/rejected_jobs.html")
```

The browser auto-open still targets `apply_list.html` only (no behaviour change).

## Call site in `run()`

After the existing `_write_html_report()` and `_write_rejected()` calls, add:

```python
_write_rejected_html(rejected)
```

`rejected` is already computed inline in `_write_rejected()`; it needs to be extracted into a local variable so both functions can use it, or `_write_rejected_html` can re-derive it the same way.

## Out of scope

- Navigation links between the two pages
- Filtering/sorting UI in the browser
- JSON API endpoint
- Pagination
