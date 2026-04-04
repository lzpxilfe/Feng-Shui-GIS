"""Benchmark manifest builder used by scripts and tests."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUDGET_PATH = ROOT / "examples" / "performance_budget.template.json"


def _sha256_text(text: str) -> str:
    digest = hashlib.sha256()
    digest.update(text.encode("utf-8"))
    return digest.hexdigest()


def _sha256_file(path: Path | str) -> str:
    if not str(path):
        return ""
    digest = hashlib.sha256()
    file_path = Path(path)
    if not file_path.is_file():
        return ""
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path | str) -> Dict[str, Any]:
    file_path = Path(path)
    if not file_path.is_file():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def _artifact(path: str, *, required: bool = True) -> Dict[str, Any]:
    if not path:
        return {"path": "", "exists": False, "sha256": ""}
    exists = Path(path).is_file()
    if required and not exists:
        return {"path": str(path), "exists": False, "sha256": ""}
    return {
        "path": str(path),
        "exists": bool(exists),
        "sha256": _sha256_file(path),
    }


def _check_status(actual: float | None, budget_max: float | None) -> str:
    if budget_max is None or actual is None:
        return "missing"
    return "ok" if actual <= float(budget_max) else "over_budget"


class BenchmarkManifestWriter:
    """Build reproducible benchmark manifests for analysis and compare/calibration."""

    DEFAULT_BUDGET_PATH = DEFAULT_BUDGET_PATH

    @staticmethod
    def infer_benchmark_tier(run_manifest: Dict[str, Any], service_name: str, runtime_seconds: float) -> str:
        del service_name
        feature_count = 0
        output_layers = run_manifest.get("output_layers") or {}
        if isinstance(output_layers, dict):
            for layer_summary in output_layers.values():
                if isinstance(layer_summary, dict):
                    feature_count = max(feature_count, int(layer_summary.get("feature_count", 0) or 0))
        source_layers = run_manifest.get("source_layers") or {}
        if isinstance(source_layers, dict):
            for layer_summary in source_layers.values():
                if isinstance(layer_summary, dict):
                    feature_count = max(feature_count, int(layer_summary.get("feature_count", 0) or 0))

        runtime = float(runtime_seconds or 0.0)
        if feature_count >= 1000 or runtime >= 120.0:
            return "large"
        if feature_count >= 250 or runtime >= 45.0:
            return "medium"
        return "small"

    @staticmethod
    def build_manifest(
        *,
        dataset_id: str,
        service_name: str,
        qgis_version: str,
        runtime_seconds: float,
        peak_memory_mb: float | str,
        cancel_latency_ms: float | str = "",
        run_manifest: Dict[str, Any],
        benchmark_tier: str,
        notes: str,
        run_manifest_path: str = "",
        report_json_path: str = "",
        report_md_path: str = "",
        budget_template_path: str = str(DEFAULT_BUDGET_PATH),
    ) -> Dict[str, Any]:
        del run_manifest
        budgets = _read_json(budget_template_path)
        service_budgets = (
            (budgets.get("budgets") or {}).get(service_name) or {}
        )
        service_budget = service_budgets.get(benchmark_tier) or {}
        runtime = float(runtime_seconds)
        peak = float(peak_memory_mb) if peak_memory_mb not in (None, "") else None
        cancel = float(cancel_latency_ms) if cancel_latency_ms not in (None, "") else None

        checks = {
            "runtime_seconds": _check_status(runtime, _coalesce(service_budget.get("runtime_seconds_max"))),
            "peak_memory_mb": _check_status(peak, _coalesce(service_budget.get("peak_memory_mb_max"))),
            "cancel_latency_ms": _check_status(cancel, _coalesce(service_budget.get("cancel_latency_ms_max"))),
        }
        if "over_budget" in checks.values():
            overall = "over_budget"
        elif all(value == "ok" for value in checks.values()):
            overall = "ok"
        else:
            overall = "missing"

        return {
            "schema_version": 2,
            "dataset": {
                "id": str(dataset_id),
                "benchmark_tier": benchmark_tier,
                "qgis_version": str(qgis_version),
            },
            "service": {
                "name": str(service_name),
                "runtime_seconds": runtime,
                "peak_memory_mb": peak,
                "cancel_latency_ms": cancel,
            },
            "artifacts": {
                "run_manifest": _artifact(run_manifest_path),
                "report_json": _artifact(report_json_path),
                "report_markdown": _artifact(report_md_path),
            },
            "budget": {
                "service": str(service_name),
                "tier": benchmark_tier,
                "status": overall,
                "limits": service_budget,
                "checks": checks,
            },
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "notes": notes or "",
        }


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return float(value)
    return None
