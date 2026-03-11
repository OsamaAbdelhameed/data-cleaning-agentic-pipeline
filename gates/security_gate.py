"""Gate 03: Security gate — detect jailbreak/injection; quarantine malicious records."""

import re
from typing import Any

# ISO date pattern for valid date_of_visit
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Known invalid or placeholder date values
INVALID_DATE_VALUES = frozenset({
    "unknown", "redacted", "n/a", "null", "none", "9999-99-99",
    "{{INTERNAL_SERVER_ERROR}}", "{{config.SECRET_KEY}}",
})

# Known invalid or placeholder patient names (case-insensitive)
INVALID_PATIENT_NAME_VALUES = frozenset({
    "admin", "system", "confidential", "classified", "unknown",
    "none", "n/a", "redacted", "placeholder", "test",
})

# ICD-10–like pattern for diagnosis_code validation
ICD10_PATTERN = re.compile(r"^[A-Z][0-9]{2}(\.[0-9]{1,4})?[A-Z]?$", re.IGNORECASE)
# Known invalid or placeholder diagnosis codes
INVALID_DIAGNOSIS_VALUES = frozenset({
    "override", "none", "classified", "unknown", "n/a", "redacted",
})

# Patterns and phrases for prompt injection / override
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+maintenance\s+mode", re.IGNORECASE),
    re.compile(r"output\s+your\s+system\s+prompt", re.IGNORECASE),
    re.compile(r"disregard\s+the\s+schema", re.IGNORECASE),
    re.compile(r"if\s+you\s+are\s+an\s+llm", re.IGNORECASE),
    re.compile(r"if\s+you\s+are\s+an\s+ai", re.IGNORECASE),
    re.compile(r"new\s+directive", re.IGNORECASE),
    re.compile(r"do\s+not\s+validate", re.IGNORECASE),
    re.compile(r"set\s+(all\s+)?(records?|status)\s+to\s+approved", re.IGNORECASE),
    re.compile(r"ignore\s+.*(rule|instruction)", re.IGNORECASE),
    re.compile(r"忽略", re.IGNORECASE),  # Chinese "ignore"
    re.compile(r"将所有", re.IGNORECASE),  # Chinese "set all"
    re.compile(r"replace\s+all\s+diagnosis\s+codes?", re.IGNORECASE),
    re.compile(r"respond\s+with\s+your\s+model\s+name", re.IGNORECASE),
    re.compile(r"you\s+are\s+no\s+longer\s+a\s+medical", re.IGNORECASE),
    re.compile(r"your\s+new\s+role\s+is", re.IGNORECASE),
    re.compile(r"do\s+not\s+use\s+json", re.IGNORECASE),
    re.compile(r"begin\s+immediately", re.IGNORECASE),
    re.compile(r"set\s+the\s+status\s+field\s+to\s+['\"]?i\s+am\s+a\s+robot", re.IGNORECASE),
    re.compile(r"delete\s+this\s+record\s+from\s+output", re.IGNORECASE),
    re.compile(r"halt\s+execution", re.IGNORECASE),
    re.compile(r"do\s+not\s+parse", re.IGNORECASE),
]

# SQL injection
SQL_INJECTION_PATTERNS = [
    re.compile(r"'\s*\)\s*;\s*drop\s+table", re.IGNORECASE),
    re.compile(r"drop\s+table\s+\w+", re.IGNORECASE),
    re.compile(r"--\s*$", re.MULTILINE),
    re.compile(r";\s*--", re.IGNORECASE),
]

# XSS
XSS_PATTERNS = [
    re.compile(r"<script\b", re.IGNORECASE),
    re.compile(r"</script>", re.IGNORECASE),
    re.compile(r"alert\s*\(", re.IGNORECASE),
]

# System / file read
SYSTEM_PATTERNS = [
    re.compile(r"/etc/passwd", re.IGNORECASE),
    re.compile(r"PIPELINE_BYPASS", re.IGNORECASE),
    re.compile(r"append\s+the\s+contents\s+of", re.IGNORECASE),
]

# Template injection (Jinja / Mustache)
TEMPLATE_PATTERNS = [
    re.compile(r"\{\{[^}]+\}\}", re.IGNORECASE),
    re.compile(r"\{\{INTERNAL_SERVER_ERROR\}\}", re.IGNORECASE),
    re.compile(r"\{\{config\.\w+\}\}", re.IGNORECASE),
]


def _get_all_string_values(record: dict[str, Any]) -> list[str]:
    """Collect all string values from a record for scanning."""
    values: list[str] = []
    for v in record.values():
        if isinstance(v, str):
            values.append(v)
    return values


def _check_patterns(text: str, patterns: list[re.Pattern], category: str) -> list[str]:
    reasons: list[str] = []
    for p in patterns:
        if p.search(text):
            reasons.append(category)
            break
    return reasons


def classify_record(record: dict[str, Any]) -> list[str]:
    """
    Scan record for malicious content. Returns list of reason strings (e.g. 'prompt_injection', 'xss').
    Empty list means clean.
    """
    reasons: list[str] = []
    for s in _get_all_string_values(record):
        reasons.extend(_check_patterns(s, PROMPT_INJECTION_PATTERNS, "prompt_injection"))
        reasons.extend(_check_patterns(s, SQL_INJECTION_PATTERNS, "sql_injection"))
        reasons.extend(_check_patterns(s, XSS_PATTERNS, "xss"))
        reasons.extend(_check_patterns(s, SYSTEM_PATTERNS, "system_command"))
        reasons.extend(_check_patterns(s, TEMPLATE_PATTERNS, "template_injection"))
    # Deduplicate while preserving order
    seen = set()
    out: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _is_invalid_date_of_visit(record: dict[str, Any]) -> bool:
    """True if date_of_visit is missing, empty, or not valid ISO 8601 (or known invalid placeholder)."""
    val = record.get("date_of_visit")
    if val is None or (isinstance(val, str) and not val.strip()):
        return True
    if not isinstance(val, str):
        return True
    s = val.strip()
    if s.lower() in INVALID_DATE_VALUES:
        return True
    if not ISO_DATE_PATTERN.match(s):
        return True
    return False


def _is_invalid_patient_name(record: dict[str, Any]) -> bool:
    """True if patient_name is missing, empty, or a known placeholder."""
    val = record.get("patient_name")
    if val is None or (isinstance(val, str) and not val.strip()):
        return True
    if not isinstance(val, str):
        return True
    if val.strip().lower() in INVALID_PATIENT_NAME_VALUES:
        return True
    return False


def _is_invalid_diagnosis_code(record: dict[str, Any]) -> bool:
    """True if diagnosis_code is missing, empty, or not valid ICD-10 (or known placeholder)."""
    val = record.get("diagnosis_code")
    if val is None or (isinstance(val, str) and not val.strip()):
        return True
    if not isinstance(val, str):
        return True
    s = val.strip()
    if s.lower() in INVALID_DIAGNOSIS_VALUES:
        return True
    if not ICD10_PATTERN.match(s):
        return True
    return False


def get_all_quarantine_reasons(record: dict[str, Any]) -> list[str]:
    """
    Return all applicable quarantine reasons: security (injection, xss, etc.) plus
    invalid_date_of_visit, invalid_patient_name, and invalid_diagnosis_code when applicable.
    Invalid-field reasons are only added when at least one security reason exists, so the
    list is complete for quarantined records without changing which records get quarantined.
    """
    reasons = list(classify_record(record))
    if reasons:
        if _is_invalid_date_of_visit(record):
            reasons.append("invalid_date_of_visit")
        if _is_invalid_patient_name(record):
            reasons.append("invalid_patient_name")
        if _is_invalid_diagnosis_code(record):
            reasons.append("invalid_diagnosis_code")
    # Deduplicate while preserving order
    seen = set()
    out: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def run_security_gate(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Classify each record as clean or quarantined. Quarantined records get a
    'quarantine_reason' field listing all applicable reasons (security + invalid_date_of_visit +
    invalid_patient_name when applicable).
    Returns (clean_records, quarantined_records).
    """
    clean: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for rec in records:
        reasons = get_all_quarantine_reasons(rec)
        if reasons:
            rec_copy = dict(rec)
            rec_copy["quarantine_reason"] = reasons
            quarantined.append(rec_copy)
        else:
            clean.append(rec)
    return clean, quarantined
