# -*- coding: utf-8 -*-
"""Pure helpers for benchmark and run-manifest persistence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


class BenchmarkManifestWriter:
    ROOT = Path(__file__).resolve().parents[2]
    DEFAULT_BUDGET_PATH = ROOT / "examples" / "performance_budget.template.json"
    _TIER_THRESHOLDS = {
        "analysis": {"medium": 250, "large": 2000},
        "compare": {"medium": 250, "large": 2000},
        "calibration": {"medium": 100, "large": 1000},
        "term_extraction": {"medium": 500, "large": 5000},
    }

    @staticmethod
    def _utc_now():
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        )

    @staticmethod
    def _safe_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def sha256_file(cls, path):
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def artifact_payload(cls, path_text):
        if not path_text:
            return {"path": "", "exists": False, "sha256": ""}
        path = Path(path_text)
        exists = path.is_file()
        return {
            "path": str(path),
            "exists": exists,
            "sha256": cls.sha256_file(path) if exists else "",
        }

    @classmethod
    def load_budget(cls, budget_template_path, service_name, benchmark_tier):
        budget_path = (
            Path(budget_template_path)
            if budget_template_path
            else cls.DEFAULT_BUDGET_PATH
        )
        template = json.loads(budget_path.read_text(encoding="utf-8"))
        tier_budget = (
            (template.get("budgets", {}) or {})
            .get(service_name, {})
            .get(benchmark_tier, {})
        )
        return {
            "path": str(budget_path),
            "service": service_name,
            "tier": benchmark_tier,
            "runtime_seconds_max": cls._safe_float(
                tier_budget.get("runtime_seconds_max")
            ),
            "peak_memory_mb_max": cls._safe_float(
                tier_budget.get("peak_memory_mb_max")
            ),
            "cancel_latency_ms_max": cls._safe_int(
                tier_budget.get("cancel_latency_ms_max")
            ),
        }

    @classmethod
    def infer_benchmark_tier(cls, run_manifest, service_name, runtime_seconds=None):
        thresholds = cls._TIER_THRESHOLDS.get(
            service_name,
            cls._TIER_THRESHOLDS["analysis"],
        )
        feature_counts = []
        if isinstance(run_manifest, dict):
            for block_name in ("source_layers", "output_layers"):
                block = run_manifest.get(block_name)
                if not isinstance(block, dict):
                    continue
                for contract in block.values():
                    if not isinstance(contract, dict):
                        continue
                    count = cls._safe_int(contract.get("feature_count"))
                    if count is not None and count > 0:
                        feature_counts.append(count)
        max_count = max(feature_counts or [0])
        if max_count >= thresholds["large"]:
            return "large"
        if max_count >= thresholds["medium"]:
            return "medium"
        runtime_value = cls._safe_float(runtime_seconds)
        if runtime_value is not None:
            if runtime_value >= 90.0:
                return "large"
            if runtime_value >= 30.0:
                return "medium"
        return "small"

    @classmethod
    def budget_status(
        cls,
        *,
        budget,
        runtime_seconds,
        peak_memory_mb,
        cancel_latency_ms,
    ):
        metric_rows = {
            "runtime_seconds": (
                cls._safe_float(runtime_seconds),
                cls._safe_float((budget or {}).get("runtime_seconds_max")),
            ),
            "peak_memory_mb": (
                cls._safe_float(peak_memory_mb),
                cls._safe_float((budget or {}).get("peak_memory_mb_max")),
            ),
            "cancel_latency_ms": (
                cls._safe_int(cancel_latency_ms),
                cls._safe_int((budget or {}).get("cancel_latency_ms_max")),
            ),
        }
        checks = {}
        has_any_check = False
        over_budget = False
        for metric_name, (observed, maximum) in metric_rows.items():
            if observed is None or maximum is None:
                checks[metric_name] = "not_recorded"
                continue
            has_any_check = True
            if observed <= maximum:
                checks[metric_name] = "within_budget"
            else:
                checks[metric_name] = "over_budget"
                over_budget = True
        if not has_any_check:
            overall = "insufficient_data"
        elif over_budget:
            overall = "over_budget"
        else:
            overall = "within_budget"
        return {"status": overall, "checks": checks}

    @classmethod
    def build_manifest(
        cls,
        *,
        dataset_id,
        service_name,
        qgis_version,
        runtime_seconds,
        peak_memory_mb=None,
        cancel_latency_ms=None,
        run_manifest=None,
        run_manifest_path="",
        report_json_path="",
        report_md_path="",
        benchmark_tier="",
        budget_template_path="",
        notes="",
    ):
        runtime_value = cls._safe_float(runtime_seconds) or 0.0
        peak_memory_value = cls._safe_float(peak_memory_mb)
        cancel_latency_value = cls._safe_int(cancel_latency_ms)
        tier = benchmark_tier or cls.infer_benchmark_tier(
            run_manifest,
            service_name,
            runtime_seconds=runtime_value,
        )
        budget = cls.load_budget(
            budget_template_path,
            service_name,
            tier,
        )
        budget_eval = cls.budget_status(
            budget=budget,
            runtime_seconds=runtime_value,
            peak_memory_mb=peak_memory_value,
            cancel_latency_ms=cancel_latency_value,
        )
        run_reference = {}
        if isinstance(run_manifest, dict):
            run_reference = {
                "run_id": str(run_manifest.get("run_id") or ""),
                "request_signature": str(run_manifest.get("request_signature") or ""),
                "report_signature": str(run_manifest.get("report_signature") or ""),
                "service_name": str(run_manifest.get("service_name") or service_name),
            }
        return {
            "schema_version": 1,
            "generated_at_utc": cls._utc_now(),
            "dataset": {
                "id": str(dataset_id or run_reference.get("run_id") or ""),
                "benchmark_tier": tier,
            },
            "service": {
                "name": service_name,
                "qgis_version": str(qgis_version or ""),
                "runtime_seconds": runtime_value,
                "peak_memory_mb": peak_memory_value,
                "cancel_latency_ms": cancel_latency_value,
            },
            "run_reference": run_reference,
            "budget": {
                **budget,
                **budget_eval,
            },
            "artifacts": {
                "run_manifest": cls.artifact_payload(run_manifest_path),
                "report_json": cls.artifact_payload(report_json_path),
                "report_markdown": cls.artifact_payload(report_md_path),
            },
            "notes": str(notes or ""),
        }

    @staticmethod
    def write_json(path, payload):
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return str(output_path)
