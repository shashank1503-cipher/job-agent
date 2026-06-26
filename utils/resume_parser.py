"""Parse a resume PDF and propose updates to preferences.yaml keyword sections.

Usage:
    python utils/resume_parser.py path/to/resume.pdf
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

import pdfplumber
import yaml

# Ensure project root is on sys.path when run directly as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.claude_client import ClaudeClient  # noqa: E402

PREFS_PATH = Path(__file__).parent.parent / "data" / "preferences.yaml"

ALLOWED_SECTIONS = ("keywords_must_have", "keywords_nice_to_have", "experience_years")

_SYSTEM = (
    "You are a technical resume analyser. Extract skills and experience from the resume text. "
    "Return ONLY valid JSON, no preamble, no markdown fences, no explanation. "
    "The JSON must match this exact shape:\n"
    "{\n"
    '  "keywords_must_have": ["Python", "REST API", ...],\n'
    '  "keywords_nice_to_have": {\n'
    '    "tier1": ["FastAPI", ...],\n'
    '    "tier2": ["Docker", ...]\n'
    "  },\n"
    '  "experience_years": { "min": 2, "max": 5 }\n'
    "}\n\n"
    "Rules:\n"
    "- Only include technologies/skills explicitly evidenced in the resume text.\n"
    "- Do not invent or infer beyond what is explicitly present.\n"
    "- keywords_must_have: core backend/language/framework skills that appear prominently.\n"
    "- tier1: frameworks/tools the candidate has significant hands-on experience with.\n"
    "- tier2: tools/technologies mentioned but less central.\n"
    "- experience_years: derive from stated years of experience or career history dates."
)


def parse_pdf(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages).strip()


def call_claude(resume_text: str, prefs_raw: str) -> dict:
    client = ClaudeClient()
    user_msg = (
        "Current preferences.yaml content (for context only — do not echo it back):\n"
        f"<preferences>\n{prefs_raw}\n</preferences>\n\n"
        f"Resume text:\n<resume>\n{resume_text}\n</resume>\n\n"
        "Return ONLY the JSON object. No preamble."
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_msg},
        ],
    )
    raw = response.content[0].text.strip()
    # Strip markdown code fences if Claude includes them despite instructions
    if raw.startswith("```"):
        parts = raw.split("```")
        inner = parts[1] if len(parts) > 1 else parts[0]
        if inner.startswith("json"):
            inner = inner[4:]
        raw = inner.strip()
    return json.loads(raw)


def _fmt_list(items) -> str:
    if not items:
        return "  (empty)"
    return "\n".join(f"  - {i}" for i in items)


def _fmt_tiered(cfg) -> str:
    if isinstance(cfg, dict):
        t1, t2 = cfg.get("tier1", []), cfg.get("tier2", [])
    else:
        t1, t2 = [], (cfg or [])
    lines = (
        ["  tier1:"]
        + ([f"    - {i}" for i in t1] or ["    (empty)"])
        + ["  tier2:"]
        + ([f"    - {i}" for i in t2] or ["    (empty)"])
    )
    return "\n".join(lines)


def _fmt_exp(cfg) -> str:
    if isinstance(cfg, dict):
        return f"  min: {cfg.get('min', '?')}  max: {cfg.get('max', '?')}"
    return f"  {cfg}"


def show_diff(section: str, current, proposed) -> None:
    print(f"\n{'─' * 60}")
    print(f"  Section : {section}")
    print(f"{'─' * 60}")
    for label, val in (("CURRENT ", current), ("PROPOSED", proposed)):
        print(f"  {label}:")
        if section == "keywords_nice_to_have":
            print(_fmt_tiered(val))
        elif section == "experience_years":
            print(_fmt_exp(val))
        else:
            print(_fmt_list(val))


def prompt_yn(question: str) -> bool:
    while True:
        ans = input(f"\n{question} [y/n]: ").strip().lower()
        if ans in ("y", "n"):
            return ans == "y"
        print("  Please enter y or n.")


def patch_prefs(accepted: dict) -> None:
    """Backup preferences.yaml then write only accepted sections."""
    bak_path = PREFS_PATH.with_suffix(".yaml.bak")
    shutil.copy2(PREFS_PATH, bak_path)
    print(f"\n  Backup written → {bak_path}")

    data = yaml.safe_load(PREFS_PATH.read_text(encoding="utf-8"))
    # Handle both wrapped (preferences: {...}) and unwrapped YAML
    target = data["preferences"] if isinstance(data.get("preferences"), dict) else data
    for section, value in accepted.items():
        target[section] = value

    PREFS_PATH.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"  preferences.yaml updated — patched: {', '.join(accepted)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse a resume PDF and propose keyword updates to preferences.yaml"
    )
    parser.add_argument("resume_path", help="Path to resume PDF")
    args = parser.parse_args()

    resume_path = Path(args.resume_path)
    if not resume_path.exists():
        print(f"Error: file not found — {resume_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing PDF: {resume_path}")
    resume_text = parse_pdf(resume_path)
    if not resume_text:
        print("Error: no text extracted from PDF.", file=sys.stderr)
        sys.exit(1)
    print(f"  Extracted {len(resume_text)} characters.")

    prefs_raw = PREFS_PATH.read_text(encoding="utf-8")

    print("\nCalling Claude to analyse resume...")
    proposed = call_claude(resume_text, prefs_raw)

    # Drop any keys Claude returned outside the allowed set
    extra = set(proposed.keys()) - set(ALLOWED_SECTIONS)
    if extra:
        print(f"  Warning: ignoring unexpected keys from Claude: {sorted(extra)}")
        for k in extra:
            del proposed[k]

    current_prefs = yaml.safe_load(prefs_raw)
    current_prefs = (
        current_prefs.get("preferences", current_prefs)
        if isinstance(current_prefs.get("preferences"), dict)
        else current_prefs
    )

    accepted: dict = {}
    for section in ALLOWED_SECTIONS:
        if section not in proposed:
            print(f"\n  Skipping {section}: not returned by Claude.")
            continue
        show_diff(section, current_prefs.get(section), proposed[section])
        if prompt_yn(f"Apply proposed {section}?"):
            accepted[section] = proposed[section]

    if not accepted:
        print("\nNo sections accepted. preferences.yaml unchanged.")
        return

    patch_prefs(accepted)
    print("\nDone.")


if __name__ == "__main__":
    main()
