"""CLI entry: load JSON, run pipeline, write cleaned_output.json and quarantined.json."""

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from config import DEFAULT_CLEAN_OUTPUT_PATH, DEFAULT_INPUT_PATH, DEFAULT_QUARANTINE_PATH
from pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the agentic data cleaning pipeline on a medical records JSON dump.",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Path to input JSON file (default: raw_dump.json)",
    )
    parser.add_argument(
        "--clean-out",
        "-o",
        type=Path,
        default=DEFAULT_CLEAN_OUTPUT_PATH,
        help="Path for cleaned output JSON (default: cleaned_output.json)",
    )
    parser.add_argument(
        "--quarantine",
        "-q",
        type=Path,
        default=DEFAULT_QUARANTINE_PATH,
        help="Path for quarantined records JSON (default: quarantined.json)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        logger.error("Input file not found: %s", args.input)
        sys.exit(1)

    logger.info("Running pipeline on %s", args.input)
    cleaned, quarantined = run_pipeline(input_path=args.input)

    args.clean_out.parent.mkdir(parents=True, exist_ok=True)
    args.quarantine.parent.mkdir(parents=True, exist_ok=True)

    with open(args.clean_out, "w") as f:
        json.dump(cleaned, f, indent=2)

    with open(args.quarantine, "w") as f:
        json.dump(quarantined, f, indent=2)

    total = len(cleaned) + len(quarantined)
    logger.info("Pipeline complete. Clean: %d | Quarantined: %d | Total output: %d", len(cleaned), len(quarantined), total)
    logger.info("Cleaned output: %s", args.clean_out)
    logger.info("Quarantined: %s", args.quarantine)


if __name__ == "__main__":
    main()
