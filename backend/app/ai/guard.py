"""Guard against AI-invented numbers.

Every rupee amount that appears in AI-written text must match (to the nearest rupee)
an amount the backend calculated. If not, the AI text is discarded and a
deterministic template is shown instead.
"""
import re

_AMOUNT = re.compile(r"(?:₹|\brs\.?|\binr)\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:rupees|rs\b)", re.I)


def amounts_in_text(text: str) -> list[int]:
    """All rupee amounts mentioned in text, in paise."""
    out = []
    for m in _AMOUNT.finditer(text):
        raw = (m.group(1) or m.group(2)).replace(",", "")
        if not raw or raw == ".":
            continue
        try:
            out.append(round(float(raw) * 100))
        except ValueError:
            continue
    return out


def unknown_amounts(text: str, allowed_paise: set[int]) -> list[int]:
    """Amounts (paise) in text that don't match any calculated value to the nearest rupee."""
    allowed = {abs(a) for a in allowed_paise}
    return [x for x in amounts_in_text(text) if not any(abs(x - a) < 100 for a in allowed)]


def only_known_amounts(text: str, allowed_paise: set[int]) -> bool:
    return not unknown_amounts(text, allowed_paise)


_MD_BOLD = re.compile(r"(\*\*|__)(.+?)\1")
_MD_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.M)
_MD_BULLET = re.compile(r"^\s*[*-]\s+", re.M)


def clean_text(text: str) -> str:
    """Strip simple markdown (bold, headings, bullets) since the UI shows plain text."""
    text = _MD_BOLD.sub(r"\2", text)
    text = _MD_HEADING.sub("", text)
    text = _MD_BULLET.sub("• ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
