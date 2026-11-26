"""Money helpers. All amounts are stored as integer paise (₹1 = 100 paise)."""

# ₹1 crore upper bound for any single amount — guards against typos like extra zeros.
MAX_AMOUNT_PAISE = 1_00_00_000 * 100


def format_inr(paise: int) -> str:
    """Format paise as an Indian-grouped rupee string, e.g. 123456789 -> '₹12,34,567.89'."""
    sign = "-" if paise < 0 else ""
    rupees, p = divmod(abs(paise), 100)
    s = str(rupees)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return f"{sign}₹{s}.{p:02d}" if p else f"{sign}₹{s}"
