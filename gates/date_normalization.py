"""Gate 02: Date normalization — all date_of_visit to ISO 8601 (YYYY-MM-DD). Reference: March 9, 2026."""

import re
from datetime import date, timedelta
from typing import Any

import dateparser

from config import REFERENCE_DATE


# ISO date pattern
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# US-style MM/DD/YYYY or YYYY/MM/DD
SLASH_DATE_PATTERN = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$|^(\d{1,2})/(\d{1,2})/(\d{4})$")


def _parse_relative(date_str: str, reference: date) -> date | None:
    """Parse relative phrases like 'yesterday', 'today', '3 days ago', 'last Tuesday', '2 weeks ago'."""
    if not date_str or not isinstance(date_str, str):
        return None
    s = date_str.strip().lower()
    if s == "today":
        return reference
    if s == "yesterday":
        return reference - timedelta(days=1)
    if s == "tomorrow":
        return reference + timedelta(days=1)

    # "N days ago"
    m = re.match(r"^(\d+)\s*days?\s*ago$", s)
    if m:
        n = int(m.group(1))
        return reference - timedelta(days=n)

    # "N weeks ago"
    m = re.match(r"^(\d+)\s*weeks?\s*ago$", s)
    if m:
        n = int(m.group(1))
        return reference - timedelta(weeks=n)

    # "last Tuesday" etc.
    if s.startswith("last "):
        parsed = dateparser.parse(date_str, settings={"RELATIVE_BASE": reference})
        if parsed:
            return parsed.date()

    # "2 weeks before 2026-03-09" or "N weeks before YYYY-MM-DD"
    m = re.search(r"(\d+)\s*weeks?\s*before\s*(\d{4}-\d{2}-\d{2})", s, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        base = date.fromisoformat(m.group(2))
        return base - timedelta(weeks=n)

    # "N days ago" already handled; try dateparser as fallback for "3 days ago" etc.
    parsed = dateparser.parse(
        date_str,
        settings={"RELATIVE_BASE": reference, "PREFER_DATES_FROM": "past"},
    )
    if parsed:
        return parsed.date()
    return None


def _parse_slash_format(date_str: str) -> date | None:
    """Parse 2026/02/01 or 02/20/2026."""
    if not date_str or not isinstance(date_str, str):
        return None
    s = date_str.strip()
    # YYYY/MM/DD
    m = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})$", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    # MM/DD/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    return None


def normalize_date(date_value: str | None, reference: date = REFERENCE_DATE) -> str | None:
    """
    Normalize a date string to ISO 8601 YYYY-MM-DD.
    Returns None if unparseable (caller can leave as-is or set null).
    """
    if date_value is None or (isinstance(date_value, str) and not date_value.strip()):
        return None
    s = str(date_value).strip()

    if ISO_DATE_PATTERN.match(s):
        try:
            date.fromisoformat(s)
            return s
        except ValueError:
            pass

    d = _parse_relative(s, reference)
    if d is not None:
        return d.isoformat()

    d = _parse_slash_format(s)
    if d is not None:
        return d.isoformat()

    # dateparser for other formats
    parsed = dateparser.parse(s)
    if parsed:
        return parsed.date().isoformat()
    return None


def run_date_normalization(
    records: list[dict[str, Any]],
    reference_date: date | None = None,
) -> list[dict[str, Any]]:
    """
    Normalize date_of_visit for each record to ISO 8601.
    Uses reference_date (default REFERENCE_DATE = 2026-03-09) for relative dates.
    Records are copied; date_of_visit is updated when parseable.
    """
    ref = reference_date or REFERENCE_DATE
    out: list[dict[str, Any]] = []
    for rec in records:
        rec = dict(rec)
        dov = rec.get("date_of_visit")
        normalized = normalize_date(dov, ref)
        if normalized is not None:
            rec["date_of_visit"] = normalized
        out.append(rec)
    return out
