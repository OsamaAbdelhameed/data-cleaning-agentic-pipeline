"""Gate 01: Schema validation — split records into valid (canonical) vs needs_healing."""

from typing import Any

from schema import (
    CANONICAL_FIELDS,
    NON_CANONICAL_KEYS,
    record_matches_canonical,
    validate_and_parse,
)


def run_schema_validation(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Validate each record against the canonical schema.
    Returns (valid_records, needs_healing).
    - valid_records: have canonical keys and pass validate_and_parse (shape + types + ISO date + ICD-10).
    - needs_healing: non-canonical keys, missing/extra keys, or validation errors (fragmented/malformed).
    """
    valid_records: list[dict[str, Any]] = []
    needs_healing: list[dict[str, Any]] = []

    for rec in records:
        if not isinstance(rec, dict):
            needs_healing.append(rec if isinstance(rec, dict) else {"_raw": rec})
            continue

        keys = set(rec.keys())
        # Has non-canonical keys (encounter_note, raw_payload, etc.) → needs Fixer
        if keys & NON_CANONICAL_KEYS:
            needs_healing.append(rec)
            continue
        # Wrong set of keys
        if keys != CANONICAL_FIELDS:
            needs_healing.append(rec)
            continue
        # Shape is canonical; check types and formats
        is_valid, _ = validate_and_parse(rec)
        if is_valid:
            valid_records.append(rec)
        else:
            needs_healing.append(rec)

    return valid_records, needs_healing
