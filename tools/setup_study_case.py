#!/usr/bin/env python3
"""Prepare a reusable local study-case folder from user DEM/site inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from feng_shui_gis.study_case_tools import setup_study_case  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_dir", type=Path, help="Prepared study-case directory to create/update.")
    parser.add_argument("--dem", required=True, type=Path, help="DEM GeoTIFF path.")
    parser.add_argument("--sites", required=True, type=Path, help="Site layer path (.shp recommended).")
    parser.add_argument("--water", type=Path, help="Optional water layer path.")
    parser.add_argument("--title", default="", help="Human-readable case title.")
    parser.add_argument("--profile", default="tomb", help="Default analysis profile.")
    parser.add_argument("--culture-key", default="", help="Default culture key for later runs.")
    parser.add_argument("--period-key", default="", help="Default period key for later runs.")
    parser.add_argument(
        "--hemisphere",
        default="north",
        choices=("north", "south"),
        help="Default hemisphere for later runs.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    summary = setup_study_case(
        case_dir=(ROOT / args.case_dir).resolve()
        if not args.case_dir.is_absolute()
        else args.case_dir.resolve(),
        dem=args.dem,
        sites=args.sites,
        water=args.water,
        title=args.title,
        profile=args.profile,
        culture_key=args.culture_key,
        period_key=args.period_key,
        hemisphere=args.hemisphere,
    )
    sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
