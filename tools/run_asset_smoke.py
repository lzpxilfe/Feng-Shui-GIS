#!/usr/bin/env python3
"""Validate sample workflow assets and regression-fixture structure."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures"
SAMPLE_PROJECT_ROOT = ROOT / "examples" / "sample_project"


def _check_shapefile_bundle(path: Path) -> dict:
    if path.suffix.lower() != ".shp":
        return {
            "kind": "raster",
            "exists": path.exists(),
            "ready": path.exists(),
            "missing_files": [],
        }

    base = path.with_suffix("")
    required = [".shp", ".shx", ".dbf", ".prj"]
    missing = [str(base.with_suffix(ext)) for ext in required if not base.with_suffix(ext).exists()]
    return {
        "kind": "shapefile",
        "exists": path.exists(),
        "missing_files": missing,
        "ready": not missing,
    }


def _fixture_summary(case_dir: Path):
    case_path = case_dir / "case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    expected = case.get("expected", {})
    benchmark = case.get("benchmark", {})
    input_specs = case.get("inputs", {})
    input_summaries = []
    for key, rel_path in input_specs.items():
        path = case_dir / rel_path
        if key.lower() in {"sites", "water"} and path.suffix.lower() != ".shp":
            extra = {
                "path": str(path),
                "kind": "vector",
                "exists": path.exists(),
                "ready": path.exists(),
                "missing_files": [],
            }
        else:
            bundle = _check_shapefile_bundle(path)
            extra = {
                "path": str(path),
                "kind": bundle["kind"],
                "exists": bundle["exists"],
                "ready": bundle["ready"],
                "missing_files": bundle["missing_files"],
            }
        extra["key"] = key
        input_summaries.append(extra)

    input_ready = all(item["ready"] for item in input_summaries) and bool(input_summaries)
    return {
        "case_id": case.get("case_id", case_dir.name),
        "title": case.get("title", ""),
        "workflow": list(case.get("workflow", [])),
        "input_specs": input_specs,
        "input_check": input_summaries,
        "inputs_ready": input_ready,
        "inputs_dir": str(case_dir / "inputs"),
        "expected_files": {
            "report_contract": str(case_dir / expected.get("report_contract", "")),
            "run_manifest_contract": str(case_dir / expected.get("run_manifest_contract", "")),
            "benchmark_manifest_contract": str(case_dir / expected.get("benchmark_manifest_contract", "")),
        },
        "required_artifacts": dict(expected.get("required_artifacts", {})),
        "benchmark": {
            "mode": benchmark.get("mode", ""),
            "truth_level": benchmark.get("truth_level", ""),
            "water_policy": benchmark.get("water_policy", ""),
        },
        "score_drift_tolerance": case.get("score_drift_tolerance"),
    }


def build_summary():
    fixtures = []
    for case_dir in sorted(path for path in FIXTURE_ROOT.iterdir() if path.is_dir()):
        fixtures.append(_fixture_summary(case_dir))
    all_inputs_ready = all(row["inputs_ready"] for row in fixtures if row["input_specs"])
    return {
        "ok": True,
        "fixture_count": len(fixtures),
        "all_inputs_ready": all_inputs_ready,
        "sample_project": {
            "readme": str(SAMPLE_PROJECT_ROOT / "README.md"),
            "project_file": str(SAMPLE_PROJECT_ROOT / "sample_project.qgs"),
        },
        "fixture_cases": fixtures,
        "workflow_steps": ["analysis", "compare", "calibration", "report_generation", "manifest_generation"],
    }


def main():
    sys.stdout.write(json.dumps(build_summary(), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
