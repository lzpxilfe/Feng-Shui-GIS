#!/usr/bin/env python3
"""Build a machine-readable benchmark manifest for Feng Shui GIS operations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from feng_shui_gis.reporting.benchmark_manifest_writer import BenchmarkManifestWriter


def build_manifest(args):
    run_manifest = None
    if args.manifest:
        manifest_path = Path(args.manifest)
        if manifest_path.is_file():
            run_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return BenchmarkManifestWriter.build_manifest(
        dataset_id=args.dataset_id,
        service_name=args.service,
        qgis_version=args.qgis_version,
        runtime_seconds=args.runtime_seconds,
        peak_memory_mb=args.peak_memory_mb,
        cancel_latency_ms=args.cancel_latency_ms,
        run_manifest=run_manifest,
        run_manifest_path=args.manifest,
        report_json_path=args.report,
        report_md_path=args.markdown,
        benchmark_tier=args.benchmark_tier,
        budget_template_path=args.budget_template,
        notes=args.notes,
    )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", required=True, help="Stable dataset identifier.")
    parser.add_argument(
        "--service",
        required=True,
        choices=("analysis", "compare", "calibration", "term_extraction"),
        help="Operation that was benchmarked.",
    )
    parser.add_argument(
        "--benchmark-tier",
        required=True,
        choices=("small", "medium", "large"),
        help="Tier name used for budget comparison.",
    )
    parser.add_argument("--qgis-version", default="", help="Exact QGIS version used.")
    parser.add_argument("--runtime-seconds", required=True, help="Observed runtime in seconds.")
    parser.add_argument("--peak-memory-mb", default="", help="Observed peak memory in MB.")
    parser.add_argument(
        "--cancel-latency-ms",
        default="",
        help="Observed cancel-to-stop latency in milliseconds.",
    )
    parser.add_argument("--manifest", default="", help="Path to the run/repro manifest JSON.")
    parser.add_argument("--report", default="", help="Path to the report JSON.")
    parser.add_argument("--markdown", default="", help="Path to the report Markdown.")
    parser.add_argument(
        "--budget-template",
        default=str(BenchmarkManifestWriter.DEFAULT_BUDGET_PATH),
        help="Budget template JSON path.",
    )
    parser.add_argument("--notes", default="", help="Optional operator note.")
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
