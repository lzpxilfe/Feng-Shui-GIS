#!/usr/bin/env python3
"""Headless smoke wrapper for sample workflow contracts."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSET_SMOKE_PATH = ROOT / "tools" / "run_asset_smoke.py"


def _load_asset_smoke():
    spec = importlib.util.spec_from_file_location("run_asset_smoke", ASSET_SMOKE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Return workflow contract only.")
    return parser.parse_args()


def main():
    args = parse_args()
    asset_smoke = _load_asset_smoke()
    summary = asset_smoke.build_summary()
    try:
        import qgis.core  # noqa: F401

        qgis_available = True
    except ImportError:
        qgis_available = False

    payload = {
        "ok": True if args.dry_run or qgis_available else False,
        "dry_run": bool(args.dry_run),
        "qgis_available": qgis_available,
        "workflow_steps": summary["workflow_steps"],
        "fixture_case_ids": [row["case_id"] for row in summary["fixture_cases"]],
        "status": (
            "dry_run_contract_ready"
            if args.dry_run
            else "ready_for_headless_execution"
            if qgis_available
            else "missing_qgis_runtime"
        ),
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
