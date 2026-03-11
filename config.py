"""Pipeline configuration: reference date, paths, OpenRouter settings."""

import os
from datetime import date
from pathlib import Path

# Reference date for relative date resolution (March 9, 2026)
REFERENCE_DATE = date(2026, 3, 9)

# Default paths (can be overridden by CLI or env)
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "raw_dump.json"
DEFAULT_CLEAN_OUTPUT_PATH = PROJECT_ROOT / "cleaned_output.json"
DEFAULT_QUARANTINE_PATH = PROJECT_ROOT / "quarantined.json"

# OpenRouter
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")

# Fixer agent max iterations to avoid infinite loops
FIXER_MAX_ITERATIONS = 5
