"""Dry-run/apply the candidate attachment classification migration."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from features.candidate_attachment_migration import run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist metadata migration. Files are never moved or deleted.",
    )
    args = parser.parse_args()
    print(json.dumps({"applied": args.apply, **run(apply=args.apply)}, indent=2))


if __name__ == "__main__":
    main()
