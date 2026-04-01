#!/usr/bin/env python3
"""Headless QGIS smoke runner for the synthetic sample project."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "examples" / "sample_project"


def require_qgis():
    try:
        from qgis.core import QgsApplication  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise SystemExit(
            "QGIS Python bindings are required for tools/run_headless_smoke.py. "
            "Use tools/run_asset_smoke.py for repository-safe asset checks."
        ) from exc
    return QgsApplication


def init_qgis():
    QgsApplication = require_qgis()
    prefix = os.environ.get("QGIS_PREFIX_PATH")
    if prefix:
        QgsApplication.setPrefixPath(prefix, True)
    app = QgsApplication([], False)
    app.initQgis()
    return app


def load_layers():
    from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer  # type: ignore

    dem = QgsRasterLayer(str(SAMPLE_DIR / "sample_dem.asc"), "sample_dem")
    water = QgsVectorLayer(str(SAMPLE_DIR / "sample_water.geojson"), "sample_water", "ogr")
    sites = QgsVectorLayer(str(SAMPLE_DIR / "sample_sites.geojson"), "sample_sites", "ogr")
    invalid = [name for name, layer in (("dem", dem), ("water", water), ("sites", sites)) if not layer.isValid()]
    if invalid:
        raise SystemExit("Failed to load sample layers: " + ", ".join(invalid))
    project = QgsProject.instance()
    project.clear()
    project.addMapLayer(dem)
    project.addMapLayer(water)
    project.addMapLayer(sites)
    return sites, dem, water


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def write_markdown(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def layer_summary(layer):
    if layer is None:
        return None
    return {
        "name": str(layer.name()),
        "feature_count": int(layer.featureCount()) if hasattr(layer, "featureCount") else 0,
        "crs": str(layer.crs().authid()) if hasattr(layer, "crs") else "",
        "source": str(layer.source()) if hasattr(layer, "source") else "",
    }


def score_stats(layer):
    values = []
    for feature in layer.getFeatures():
        try:
            values.append(float(feature["fs_score"]))
        except (KeyError, TypeError, ValueError):
            continue
    if not values:
        return {"count": 0, "min": 0.0, "max": 0.0, "mean": 0.0}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / float(len(values)),
    }


def run_benchmark_cli(service_name, runtime_seconds, run_manifest_path, report_json_path, report_md_path, output_path):
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools" / "build_benchmark_manifest.py"),
            "--dataset-id",
            "sample-project-headless-smoke",
            "--service",
            service_name,
            "--benchmark-tier",
            "small",
            "--qgis-version",
            "3.28+",
            "--runtime-seconds",
            f"{runtime_seconds:.4f}",
            "--peak-memory-mb",
            "256",
            "--cancel-latency-ms",
            "600",
            "--manifest",
            str(run_manifest_path),
            "--report",
            str(report_json_path),
            "--markdown",
            str(report_md_path),
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "reports" / "headless_smoke"),
        help="Directory for generated smoke outputs.",
    )
    parser.add_argument("--profile-key", default="tomb")
    parser.add_argument("--compare-profile-key", default="tomb_kr")
    parser.add_argument("--culture-key", default="korea")
    parser.add_argument("--period-key", default="early_modern")
    parser.add_argument("--hemisphere", default="north")
    parser.add_argument("--negative-ratio", type=int, default=2)
    parser.add_argument("--random-seed", type=int, default=17)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    app = init_qgis()
    try:
        sites, dem, water = load_layers()

        from feng_shui_gis.compare_contracts import top_score_changes
        from feng_shui_gis.reporting.calibration_report_writer import CalibrationReportWriter
        from feng_shui_gis.reporting.compare_report_writer import CompareReportWriter
        from feng_shui_gis.service_contracts import AnalysisRequest, CalibrationRequest, CompareRequest
        from feng_shui_gis.services.analysis_service import FengShuiAnalysisService
        from feng_shui_gis.trust_metadata import build_trust_metadata

        service = FengShuiAnalysisService()
        summary = {
            "smoke_status": "ok",
            "sample_project": str(SAMPLE_DIR / "sample_project.qgz"),
            "generated": {},
        }

        started = time.perf_counter()
        analysis_output = service.run_analysis(
            AnalysisRequest(
                site_layer=sites,
                dem_layer=dem,
                water_layer=water,
                hemisphere=args.hemisphere,
                profile_key=args.profile_key,
                culture_key=args.culture_key,
                period_key=args.period_key,
                auto_hydro=False,
            )
        )
        analysis_runtime = time.perf_counter() - started
        analysis_manifest = output_dir / "analysis_run_manifest.json"
        analysis_json = output_dir / "analysis_report.json"
        analysis_md = output_dir / "analysis_report.md"
        analysis_benchmark = output_dir / "analysis_benchmark_manifest.json"
        write_json(analysis_manifest, analysis_output.run_manifest or {})
        analysis_payload = {
            "service": "analysis",
            "site_layer": layer_summary(sites),
            "analysis_layer": layer_summary(analysis_output.analysis_layer),
            "used_water_layer": layer_summary(analysis_output.used_water_layer),
            "run_manifest": analysis_output.run_manifest or {},
        }
        write_json(analysis_json, analysis_payload)
        write_markdown(
            analysis_md,
            "# Headless Analysis Smoke\n\n"
            f"- Profile: {args.profile_key}\n"
            f"- Culture: {args.culture_key}\n"
            f"- Period: {args.period_key}\n"
            f"- Output features: {analysis_payload['analysis_layer']['feature_count'] if analysis_payload['analysis_layer'] else 0}\n",
        )
        run_benchmark_cli("analysis", analysis_runtime, analysis_manifest, analysis_json, analysis_md, analysis_benchmark)
        summary["generated"]["analysis"] = {
            "report_json": str(analysis_json),
            "report_markdown": str(analysis_md),
            "run_manifest": str(analysis_manifest),
            "benchmark_manifest": str(analysis_benchmark),
        }

        started = time.perf_counter()
        compare_output = service.run_profile_compare(
            CompareRequest(
                site_layer=sites,
                dem_layer=dem,
                water_layer=water,
                hemisphere=args.hemisphere,
                base_profile_key=args.profile_key,
                compare_profile_key=args.compare_profile_key,
                culture_key=args.culture_key,
                period_key=args.period_key,
                auto_hydro=False,
            )
        )
        compare_runtime = time.perf_counter() - started
        compare_manifest = output_dir / "compare_run_manifest.json"
        compare_json = output_dir / "compare_report.json"
        compare_md = output_dir / "compare_report.md"
        compare_benchmark = output_dir / "compare_benchmark_manifest.json"
        write_json(compare_manifest, compare_output.run_manifest or {})
        compare_changes = top_score_changes(
            compare_output.base_layer,
            compare_output.compare_layer,
            feature_uid_resolver=lambda feature: str(feature["feature_uid"]),
            label_resolver=lambda feature: str(feature["feature_uid"]),
            reason_resolver=lambda feature: str(feature["fs_reason"] if "fs_reason" in feature.fields().names() else ""),
            limit=10,
        )
        base_stats = score_stats(compare_output.base_layer)
        compare_stats = score_stats(compare_output.compare_layer)
        delta_stats = {
            "mean_delta": float(compare_stats.get("mean", 0.0)) - float(base_stats.get("mean", 0.0)),
            "max_gain": max((float(row.get("delta", 0.0)) for row in compare_changes), default=0.0),
            "max_drop": min((float(row.get("delta", 0.0)) for row in compare_changes), default=0.0),
        }
        compare_trust = build_trust_metadata(
            "en",
            advanced_context_enabled=True,
            culture_key=args.culture_key,
            profile_key=args.compare_profile_key,
        )
        compare_payload = CompareReportWriter.payload(
            stamp="headless_smoke",
            site_layer_name=sites.name(),
            base_profile_key=args.profile_key,
            compare_profile_key=args.compare_profile_key,
            base_stats=base_stats,
            compare_stats=compare_stats,
            delta_stats=delta_stats,
            top_changes=compare_changes,
            change_layer_name="headless_compare_change",
            reason_excerpt_limit=88,
            trust_metadata=compare_trust,
        )
        write_json(compare_json, compare_payload)
        write_markdown(
            compare_md,
            CompareReportWriter.build_markdown(
                stamp="headless_smoke",
                text_lang="en",
                site_layer_name=sites.name(),
                base_profile_key=args.profile_key,
                compare_profile_key=args.compare_profile_key,
                base_stats=base_stats,
                compare_stats=compare_stats,
                delta_stats=delta_stats,
                top_changes=compare_changes,
                change_layer_name="headless_compare_change",
                reason_excerpt_limit=88,
                trust_metadata=compare_trust,
            ),
        )
        run_benchmark_cli("compare", compare_runtime, compare_manifest, compare_json, compare_md, compare_benchmark)
        summary["generated"]["compare"] = {
            "report_json": str(compare_json),
            "report_markdown": str(compare_md),
            "run_manifest": str(compare_manifest),
            "benchmark_manifest": str(compare_benchmark),
        }

        started = time.perf_counter()
        calibration_output = service.run_calibration(
            CalibrationRequest(
                site_layer=sites,
                dem_layer=dem,
                water_layer=water,
                hemisphere=args.hemisphere,
                profile_key=args.profile_key,
                culture_key=args.culture_key,
                period_key=args.period_key,
                negative_ratio=args.negative_ratio,
                random_seed=args.random_seed,
                auto_hydro=False,
            )
        )
        calibration_runtime = time.perf_counter() - started
        calibration_manifest = output_dir / "calibration_run_manifest.json"
        calibration_json = output_dir / "calibration_report.json"
        calibration_md = output_dir / "calibration_report.md"
        calibration_benchmark = output_dir / "calibration_benchmark_manifest.json"
        write_json(calibration_manifest, calibration_output.run_manifest or {})
        calibration_report = dict(calibration_output.report or {})
        calibration_report["run_manifest"] = calibration_output.run_manifest or {}
        calibration_report["trust_metadata"] = build_trust_metadata(
            "en",
            advanced_context_enabled=True,
            culture_key=args.culture_key,
            profile_key=str(calibration_report.get("exported_profile_key") or args.profile_key),
            reported_metric_phase=str(calibration_report.get("reported_metric_phase") or ""),
        )
        write_json(calibration_json, calibration_report)
        write_markdown(
            calibration_md,
            CalibrationReportWriter.build_markdown(
                report=calibration_report,
                stamp="headless_smoke",
                text_lang="en",
                metric_compare_markdown="No comparison table generated in smoke mode.",
                metadata_markdown="Synthetic sample project.",
                history_markdown="No history in smoke mode.",
                paper_evidence_summary=str(calibration_report.get("paper_evidence_summary", "") or ""),
                paper_evidence_references="",
            ),
        )
        run_benchmark_cli("calibration", calibration_runtime, calibration_manifest, calibration_json, calibration_md, calibration_benchmark)
        summary["generated"]["calibration"] = {
            "report_json": str(calibration_json),
            "report_markdown": str(calibration_md),
            "run_manifest": str(calibration_manifest),
            "benchmark_manifest": str(calibration_benchmark),
        }

        write_json(output_dir / "smoke_summary.json", summary)
        sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    finally:
        try:
            from qgis.core import QgsProject  # type: ignore

            QgsProject.instance().clear()
        except Exception:
            pass
        app.exitQgis()


if __name__ == "__main__":
    main()
