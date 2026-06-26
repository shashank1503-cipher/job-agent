import html
import re

_HTML_TAG = re.compile(r"<[^>]+>", re.DOTALL)
_MD_ESCAPE = re.compile(r"\\([+*\-.\[\]()`_{}#!>|~&])")
_SPACES = re.compile(r"[ \t]+")
_NEWLINES = re.compile(r"\n{3,}")


def _clean(text: str) -> str:
    """Strip HTML tags, unescape HTML entities and markdown escapes, collapse whitespace."""
    if not text:
        return text
    text = _HTML_TAG.sub(" ", text)
    text = html.unescape(text)
    text = _MD_ESCAPE.sub(r"\1", text)
    text = _SPACES.sub(" ", text)
    text = _NEWLINES.sub("\n\n", text)
    return text.strip()
