"""Canonical medical record schema and validation helpers."""

import re
from typing import Any

# Canonical field names
CANONICAL_FIELDS = frozenset({
    "record_id",
    "patient_name",
    "date_of_visit",
    "diagnosis_code",
    "status",
    "notes",
})

# Fields that indicate a non-canonical / fragmented record (need Fixer)
NON_CANONICAL_KEYS = frozenset({
    "encounter_note",
    "raw_payload",
    "referral_text",
    "pat",
    "vis",
    "dx",
    "source",
})

# ISO date pattern (YYYY-MM-DD)
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# ICD-10: letter + 2 digits, optional . + 1-4 digits, optional trailing character (e.g. A for initial encounter)
# Allow 1 digit after dot so codes like E11.9, M54.5, R51.9 pass
ICD10_PATTERN = re.compile(r"^[A-Z][0-9]{2}(\.[0-9]{1,4})?[A-Z]?$", re.IGNORECASE)


def normalize_patient_name(value: Any) -> str | None:
    """Capitalize patient name: replace underscores with spaces and apply title case (e.g. 'julie_mao' -> 'Julie Mao')."""
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value).replace("_", " ").strip().title() or None
    return value.replace("_", " ").strip().title() or None


def record_matches_canonical(record: dict[str, Any]) -> bool:
    """
    Return True if the record has exactly the canonical shape and types.
    Does not validate date format or ICD-10; use validate_and_parse for that.
    """
    if not isinstance(record, dict):
        return False
    keys = set(record.keys())
    if keys != CANONICAL_FIELDS:
        return False
    # Required string fields
    for field in ("record_id", "patient_name", "date_of_visit", "diagnosis_code", "status"):
        val = record.get(field)
        if val is not None and not isinstance(val, str):
            return False
        if field != "diagnosis_code" and val in (None, ""):
            return False
    # notes can be null
    notes = record.get("notes")
    if notes is not None and not isinstance(notes, str):
        return False
    return True


def validate_and_parse(record: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Check canonical shape, types, date format (ISO), and ICD-10 pattern.
    Returns (is_valid, list of error messages).
    """
    errors: list[str] = []

    if not isinstance(record, dict):
        return False, ["Record is not a dict"]

    keys = set(record.keys())
    if keys != CANONICAL_FIELDS:
        extra = keys - CANONICAL_FIELDS
        missing = CANONICAL_FIELDS - keys
        if extra:
            errors.append(f"Unexpected keys: {sorted(extra)}")
        if missing:
            errors.append(f"Missing keys: {sorted(missing)}")
        if errors:
            return False, errors

    # record_id
    rid = record.get("record_id")
    if not rid or not isinstance(rid, str):
        errors.append("record_id must be a non-empty string")

    # patient_name
    pn = record.get("patient_name")
    if pn is None or (isinstance(pn, str) and pn.strip() == ""):
        errors.append("patient_name must be a non-empty string")
    elif not isinstance(pn, str):
        errors.append("patient_name must be a string")

    # date_of_visit — must be ISO date string (YYYY-MM-DD) when present
    dov = record.get("date_of_visit")
    if dov is None or (isinstance(dov, str) and dov.strip() == ""):
        errors.append("date_of_visit is required")
    elif not isinstance(dov, str):
        errors.append("date_of_visit must be a string")
    elif not ISO_DATE_PATTERN.match(dov.strip()):
        errors.append("date_of_visit must be ISO 8601 date (YYYY-MM-DD)")

    # diagnosis_code — ICD-10 pattern when present
    dc = record.get("diagnosis_code")
    if dc is None or (isinstance(dc, str) and dc.strip() == ""):
        errors.append("diagnosis_code is required")
    elif not isinstance(dc, str):
        errors.append("diagnosis_code must be a string")
    elif not ICD10_PATTERN.match(dc.strip()):
        errors.append("diagnosis_code must be valid ICD-10 format")

    # status
    st = record.get("status")
    if st is None or (isinstance(st, str) and st.strip() == ""):
        errors.append("status must be a non-empty string")
    elif not isinstance(st, str):
        errors.append("status must be a string")

    # notes — optional, string or null
    notes = record.get("notes")
    if notes is not None and not isinstance(notes, str):
        errors.append("notes must be string or null")

    return len(errors) == 0, errors


def is_fragmented_or_malformed(record: dict[str, Any]) -> bool:
    """
    True if the record has non-canonical keys or fails canonical validation.
    Such records should be sent to the Fixer agent.
    """
    if not isinstance(record, dict):
        return True
    keys = set(record.keys())
    if keys & NON_CANONICAL_KEYS:
        return True
    if keys != CANONICAL_FIELDS:
        return True
    valid, _ = validate_and_parse(record)
    return not valid
