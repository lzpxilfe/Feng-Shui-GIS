#!/usr/bin/env python3
"""Release guard checks for productization assets, metadata, and support tooling."""

from __future__ import annotations

import configparser
import json
import tempfile
from pathlib import Path

from feng_shui_gis.reporting.support_bundle_writer import SupportBundleWriter


ROOT = Path(__file__).resolve().parents[1]


def required_paths():
    return [
        ROOT / "README.md",
        ROOT / "docs" / "first_run_guide.md",
        ROOT / "docs" / "tested_versions.md",
        ROOT / "docs" / "troubleshooting.md",
        ROOT / "docs" / "support_bundle_guide.md",
        ROOT / "docs" / "release_checklist.md",
        ROOT / "examples" / "sample_project" / "sample_project.qgz",
        ROOT / "tools" / "run_headless_smoke.py",
        ROOT / "tools" / "run_asset_smoke.py",
    ]


def validate_metadata():
    parser = configparser.ConfigParser()
    parser.read(ROOT / "feng_shui_gis" / "metadata.txt", encoding="utf-8")
    general = parser["general"]
    required = ("homepage", "repository", "tracker", "version", "qgisMinimumVersion")
    missing = [key for key in required if not str(general.get(key, "")).strip()]
    if missing:
        raise SystemExit("Missing metadata keys: " + ", ".join(missing))
    description = str(general.get("description", "")).lower()
    about = str(general.get("about", "")).lower()
    metadata_checks = {
        "heuristic": (description + " " + about),
        "predictive truth model": (description + " " + about),
        "standalone validation": about,
        "projected crs": about,
    }
    missing_phrases = [
        phrase for phrase, text in metadata_checks.items() if phrase not in text
    ]
    if missing_phrases:
        raise SystemExit(
            "Metadata is missing store-facing limitation phrases: "
            + ", ".join(missing_phrases)
        )


def validate_readme_links():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    required = (
        "sample project",
        "first run",
        "tested versions",
        "known limitations",
        "troubleshooting",
        "support bundle",
        "what this tool is not",
    )
    missing = [label for label in required if label.lower() not in text.lower()]
    if missing:
        raise SystemExit("README is missing productization sections: " + ", ".join(missing))


def validate_tested_versions_doc():
    text = (ROOT / "docs" / "tested_versions.md").read_text(encoding="utf-8").lower()
    required = (
        "qgis",
        "ubuntu",
        "known limitations",
        "projected crs",
        "predictive truth model",
        "standalone validation",
    )
    missing = [label for label in required if label not in text]
    if missing:
        raise SystemExit(
            "Tested versions / known limitations doc is incomplete: " + ", ".join(missing)
        )


def validate_sample_project_readme():
    text = (ROOT / "examples" / "sample_project" / "README.md").read_text(
        encoding="utf-8"
    ).lower()
    required = (
        "expected layers",
        "expected report examples",
        "fengshui_ridges",
        "fengshui_hydro",
        "fengshui",
    )
    missing = [label for label in required if label not in text]
    if missing:
        raise SystemExit("Sample project README is missing expected-output guidance: " + ", ".join(missing))


def validate_bug_report_template():
    text = (ROOT / "docs" / "bug_report_template.md").read_text(encoding="utf-8").lower()
    required = (
        "support bundle",
        "qgis version",
        "plugin version",
        "operating system",
    )
    missing = [label for label in required if label not in text]
    if missing:
        raise SystemExit("Bug report template is missing support fields: " + ", ".join(missing))


def validate_no_local_absolute_links():
    targets = [
        ROOT / "README.md",
        ROOT / "docs",
        ROOT / "examples" / "sample_project" / "README.md",
    ]
    offending = []
    for target in targets:
        files = [target] if target.is_file() else sorted(target.rglob("*.md"))
        for file_path in files:
            text = file_path.read_text(encoding="utf-8")
            if "/Users/" in text:
                offending.append(str(file_path.relative_to(ROOT)))
    if offending:
        raise SystemExit(
            "Markdown contains local absolute paths: " + ", ".join(offending)
        )


def validate_fixture_layout():
    fixture_root = ROOT / "tests" / "fixtures"
    expected_cases = {
        "clear_hydro_case",
        "exploratory_context_case",
        "calibration_shift_case",
    }
    found = {path.name for path in fixture_root.iterdir() if path.is_dir()}
    missing_cases = sorted(expected_cases - found)
    if missing_cases:
        raise SystemExit("Missing regression cases: " + ", ".join(missing_cases))
    for case_name in expected_cases:
        case_dir = fixture_root / case_name
        case_path = case_dir / "case.json"
        if not case_path.is_file():
            raise SystemExit(f"Missing case.json for {case_name}")
        payload = json.loads(case_path.read_text(encoding="utf-8"))
        if payload.get("case_id") != case_name:
            raise SystemExit(f"Fixture case_id mismatch for {case_name}")
        for dirname in ("inputs", "expected"):
            if not (case_dir / dirname).is_dir():
                raise SystemExit(f"Missing {dirname} directory for {case_name}")


def validate_support_bundle_writer():
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_path = Path(tmpdir) / "support_bundle_test.zip"
        SupportBundleWriter.write_bundle(
            bundle_path,
            payload_entries={
                "bundle_manifest.json": {
                    "notes": {"raw_input_policy": "references only"},
                    "trust_metadata": {"result_badges": ["general_principles"]},
                }
            },
            file_entries={},
        )
        if not bundle_path.is_file():
            raise SystemExit("Support bundle writer did not create a zip file.")


def main():
    missing = [str(path.relative_to(ROOT)) for path in required_paths() if not path.exists()]
    if missing:
        raise SystemExit("Missing required release assets: " + ", ".join(missing))
    validate_metadata()
    validate_readme_links()
    validate_tested_versions_doc()
    validate_sample_project_readme()
    validate_bug_report_template()
    validate_no_local_absolute_links()
    validate_fixture_layout()
    validate_support_bundle_writer()
    print(
        json.dumps(
            {
                "status": "ok",
                "checked": [
                    "metadata",
                    "readme",
                    "tested_versions",
                    "sample_project",
                    "bug_report_template",
                    "markdown_link_integrity",
                    "fixture_layout",
                    "support_bundle",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
