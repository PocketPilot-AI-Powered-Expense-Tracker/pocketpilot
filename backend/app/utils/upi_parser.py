"""Parse UPI payment notification text into structured fields.

Deliberately conservative: anything that does not clearly look like a
*successful debit* (money leaving the user's account) is ignored. Credits,
payment requests, failures, refunds and cashback are never turned into
pending transactions.

This is a pure function so the Android companion app can mirror the same rules.
"""
import re
from dataclasses import dataclass

SUPPORTED_APPS = ("phonepe", "gpay", "paytm", "bhim", "other")

_AMOUNT = re.compile(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)", re.I)
_REF = re.compile(r"(?:ref(?:erence)?|utr|txn|transaction)\s*(?:no\.?|id|number|#)?\s*[:\-]?\s*(\d{10,16})", re.I)
# Recipient: the first "to <name>", stopping at common trailing words or punctuation.
_COUNTERPARTY = re.compile(
    r"\bto\s+(.+?)(?=\s+(?:on|via|using|from|successfully|is|was|for|upi|ref)\b|[.,!|]|$)",
    re.I,
)
_DEBIT_WORDS = re.compile(r"\b(paid|sent|debited|payment successful|payment of|you paid)\b", re.I)
_IGNORE_WORDS = re.compile(
    r"\b(received|credited|request(?:ed|s)?|collect|failed|declined|unsuccessful|pending|"
    r"reversed|refund(?:ed)?|cashback|reward|expired|cancelled|due|reminder)\b",
    re.I,
)


@dataclass(frozen=True)
class ParsedNotification:
    amount_paise: int
    counterparty: str | None
    transaction_ref: str | None


class NotAPayment(ValueError):
    """Raised with a human-readable reason when the notification should be ignored."""


def _to_paise(raw: str) -> int:
    whole, _, frac = raw.replace(",", "").partition(".")
    return int(whole) * 100 + int(frac.ljust(2, "0")[:2] or 0)


def parse_notification(title: str, text: str) -> ParsedNotification:
    content = f"{title} {text}".strip()
    if not content:
        raise NotAPayment("The notification is empty")
    ignored = _IGNORE_WORDS.search(content)
    if ignored:
        raise NotAPayment(f"Ignored: looks like a '{ignored.group(1).lower()}' message, not a completed payment")
    if not _DEBIT_WORDS.search(content):
        raise NotAPayment("Ignored: this doesn't look like a payment you made")
    amount = _AMOUNT.search(content)
    if not amount:
        raise NotAPayment("Ignored: no rupee amount found")
    paise = _to_paise(amount.group(1))
    if paise <= 0:
        raise NotAPayment("Ignored: amount is zero")
    cp = _COUNTERPARTY.search(content)
    counterparty = cp.group(1).strip(" -:")[:60] if cp else None
    ref = _REF.search(content)
    return ParsedNotification(paise, counterparty or None, ref.group(1) if ref else None)
