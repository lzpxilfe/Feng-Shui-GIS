#!/usr/bin/env python3
"""Build a machine-readable reproducibility manifest for Feng Shui GIS runs."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = ROOT / "feng_shui_gis" / "metadata.txt"
CONFIG_DIR = ROOT / "feng_shui_gis" / "config"


def load_metadata():
    parser = configparser.ConfigParser()
    parser.read(METADATA_PATH, encoding="utf-8")
    general = parser["general"]
    return {
        "name": general.get("name", "Feng Shui GIS"),
        "version": general.get("version", ""),
        "qgis_minimum_version": general.get("qgisMinimumVersion", ""),
        "repository": general.get("repository", ""),
    }


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def config_snapshot():
    rows = []
    for path in sorted(CONFIG_DIR.glob("*.json")):
        rows.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(path),
            }
        )
    return rows


def git_commit():
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            .stdout.strip()
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""


def git_dirty():
    try:
        output = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return bool(output.strip())


def build_manifest(args):
    metadata = load_metadata()
    return {
        "dataset": {
            "id": args.dataset_id,
            "study_label": args.study_label,
            "dem_path": args.dem,
            "water_path": args.water,
            "sites_path": args.sites,
            "crs": args.crs,
        },
        "plugin": {
            "name": metadata["name"],
            "version": metadata["version"],
            "qgis_version": args.qgis_version,
            "qgis_minimum_version": metadata["qgis_minimum_version"],
        },
        "repository": {
            "url": metadata["repository"],
            "commit": args.commit or git_commit(),
            "working_tree_dirty": git_dirty(),
        },
        "config_snapshot": config_snapshot(),
        "run": {
            "run_contract_version": "2.0.0",
            "operator": args.operator,
            "generated_at_utc": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "hemisphere": args.hemisphere,
            "profile": args.profile,
            "culture_key": args.culture_key,
            "period_key": args.period_key,
            "random_seed": args.random_seed,
            "validation_ratio": args.validation_ratio,
            "split_seed": args.split_seed,
            "validation_group": args.validation_group,
            "auto_hydro": args.auto_hydro,
            "include_terms": args.include_terms,
            "notes": args.notes,
        },
        "artifacts": {
            "landscape_layer": args.landscape_layer,
            "scored_layer": args.scored_layer,
            "calibration_report_json": args.calibration_report_json,
            "calibration_report_md": args.calibration_report_md,
        },
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", default="", help="Stable dataset identifier.")
    parser.add_argument("--study-label", default="", help="Human-readable study label.")
    parser.add_argument("--operator", default="", help="Who executed the run.")
    parser.add_argument("--qgis-version", default="", help="Exact QGIS version used.")
    parser.add_argument("--dem", default="", help="Relative or absolute DEM path.")
    parser.add_argument("--water", default="", help="Relative or absolute water-layer path.")
    parser.add_argument("--sites", default="", help="Relative or absolute site-layer path.")
    parser.add_argument("--crs", default="", help="Study CRS, e.g. EPSG:5186.")
    parser.add_argument("--hemisphere", default="north", choices=("north", "south"))
    parser.add_argument("--profile", default="general")
    parser.add_argument("--culture-key", default="")
    parser.add_argument("--period-key", default="")
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--split-seed", type=int, default=1234)
    parser.add_argument("--validation-group", default="cv_holdout")
    parser.add_argument("--notes", default="")
    parser.add_argument("--commit", default="", help="Override detected git commit.")
    parser.add_argument("--landscape-layer", default="")
    parser.add_argument("--scored-layer", default="")
    parser.add_argument("--calibration-report-json", default="")
    parser.add_argument("--calibration-report-md", default="")
    parser.add_argument("--auto-hydro", action="store_true")
    parser.add_argument("--include-terms", action="store_true")
    parser.add_argument("--output", default="", help="Write JSON to this path.")
    return parser.parse_args()


def main():
    args = parse_args()
    manifest = build_manifest(args)
    text = json.dumps(manifest, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")


if __name__ == "__main__":
    main()
