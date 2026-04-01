#!/usr/bin/env python3
"""Repository-safe smoke workflow for productization assets and report manifests."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "examples" / "sample_project"


def required_sample_paths():
    return [
        SAMPLE_DIR / "sample_dem.asc",
        SAMPLE_DIR / "sample_water.geojson",
        SAMPLE_DIR / "sample_sites.geojson",
        SAMPLE_DIR / "expected_analysis_report.json",
        SAMPLE_DIR / "expected_compare_report.json",
        SAMPLE_DIR / "expected_calibration_report.md",
        SAMPLE_DIR / "sample_project.qgz",
    ]


def run_command(args):
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "reports" / "asset_smoke"),
        help="Directory for generated smoke manifests.",
    )
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    missing = [str(path.relative_to(ROOT)) for path in required_sample_paths() if not path.is_file()]
    if missing:
        raise SystemExit("Missing sample project assets: " + ", ".join(missing))

    repro_manifest = output_dir / "repro_manifest.json"
    run_command(
        [
            "python3",
            str(ROOT / "tools" / "build_repro_manifest.py"),
            "--dataset-id",
            "sample-project-asset-smoke",
            "--study-label",
            "sample project asset smoke",
            "--qgis-version",
            "3.28+",
            "--dem",
            str((SAMPLE_DIR / "sample_dem.asc").relative_to(ROOT)),
            "--water",
            str((SAMPLE_DIR / "sample_water.geojson").relative_to(ROOT)),
            "--sites",
            str((SAMPLE_DIR / "sample_sites.geojson").relative_to(ROOT)),
            "--crs",
            "LOCAL_SAMPLE_GRID",
            "--profile",
            "tomb",
            "--culture-key",
            "korea",
            "--period-key",
            "early_modern",
            "--output",
            str(repro_manifest),
        ]
    )

    benchmark_outputs = {}
    for service_name, report_name in (
        ("analysis", "expected_analysis_report.json"),
        ("compare", "expected_compare_report.json"),
        ("calibration", "expected_calibration_report.md"),
    ):
        report_json = (
            SAMPLE_DIR / report_name
            if report_name.endswith(".json")
            else output_dir / f"{service_name}_report_proxy.json"
        )
        report_md = (
            SAMPLE_DIR / report_name
            if report_name.endswith(".md")
            else output_dir / f"{service_name}_report_proxy.md"
        )
        if report_name.endswith(".json"):
            report_md.write_text(f"# {service_name} asset smoke markdown\n", encoding="utf-8")
        else:
            report_json.write_text(
                json.dumps({"service": service_name, "source": report_name}, indent=2) + "\n",
                encoding="utf-8",
            )
        benchmark_path = output_dir / f"{service_name}_benchmark_manifest.json"
        run_command(
            [
                "python3",
                str(ROOT / "tools" / "build_benchmark_manifest.py"),
                "--dataset-id",
                "sample-project-asset-smoke",
                "--service",
                service_name,
                "--benchmark-tier",
                "small",
                "--qgis-version",
                "3.28+",
                "--runtime-seconds",
                "5.0",
                "--peak-memory-mb",
                "256",
                "--cancel-latency-ms",
                "600",
                "--manifest",
                str(repro_manifest),
                "--report",
                str(report_json),
                "--markdown",
                str(report_md),
                "--output",
                str(benchmark_path),
            ]
        )
        benchmark_outputs[service_name] = str(benchmark_path)

    summary_path = output_dir / "smoke_summary.json"
    summary = {
        "sample_project_ready": True,
        "mode": "asset_smoke",
        "repro_manifest": str(repro_manifest),
        "benchmarks": benchmark_outputs,
        "sample_inputs": [str(path.relative_to(ROOT)) for path in required_sample_paths()],
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
