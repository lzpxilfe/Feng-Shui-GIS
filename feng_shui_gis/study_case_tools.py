# -*- coding: utf-8 -*-
"""Pure-Python helpers for preparing local study cases without QGIS."""

from __future__ import annotations

import json
import shutil
import struct
from pathlib import Path


REQUIRED_SHAPEFILE_SUFFIXES = (".shp", ".shx", ".dbf", ".prj")
OPTIONAL_SHAPEFILE_SUFFIXES = (".cpg",)
SHAPE_TYPE_NAMES = {
    0: "Null",
    1: "Point",
    3: "Polyline",
    5: "Polygon",
    8: "MultiPoint",
    11: "PointZ",
    13: "PolylineZ",
    15: "PolygonZ",
    18: "MultiPointZ",
    21: "PointM",
    23: "PolylineM",
    25: "PolygonM",
    28: "MultiPointM",
    31: "MultiPatch",
}

_STANDARD_COMPARE_PAIRS = (
    {"id": "context_vs_neutral", "base": "neutral", "candidate": "context"},
    {"id": "calibrated_vs_context", "base": "context", "candidate": "calibrated"},
)

_STANDARD_REQUIRED_ARTIFACTS = {
    "run_manifest": "reports/run_manifest.json",
    "benchmark_manifest": "reports/benchmark_manifest.json",
    "analysis_report": "reports/analysis_report.json",
    "compare_summary": "reports/compare_summary.json",
    "calibration_report": "reports/calibration_report.json",
    "false_positive_notes": "reports/false_positive_notes.md",
    "false_negative_notes": "reports/false_negative_notes.md",
}


def qgis_runtime_available():
    try:
        import qgis.core  # noqa: F401
    except ImportError:
        return False
    return True


def _ensure_file(path: Path, label: str) -> Path:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{label} 파일을 찾지 못했습니다: {path}")
    return path


def _decode_text(raw: bytes) -> str:
    for encoding in ("utf-8", "cp949", "euc-kr", "latin1"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore").strip()


def missing_shapefile_sidecars(path: Path):
    base = path.with_suffix("")
    return [
        str(base.with_suffix(suffix))
        for suffix in REQUIRED_SHAPEFILE_SUFFIXES
        if not base.with_suffix(suffix).exists()
    ]


def copy_with_sidecar(src: Path, dst: Path):
    src = src.expanduser().resolve()
    dst = dst.expanduser().resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src != dst:
        shutil.copy2(src, dst)
    if src.suffix.lower() != ".shp":
        return

    src_base = src.with_suffix("")
    dst_base = dst.with_suffix("")
    for suffix in REQUIRED_SHAPEFILE_SUFFIXES + OPTIONAL_SHAPEFILE_SUFFIXES:
        side_src = src_base.with_suffix(suffix)
        side_dst = dst_base.with_suffix(suffix)
        if side_src.exists() and side_src != side_dst:
            shutil.copy2(side_src, side_dst)


def inspect_raster(path: Path):
    path = path.expanduser().resolve()
    exists = path.exists()
    payload = {
        "path": str(path),
        "kind": "raster",
        "driver": path.suffix.lower().lstrip(".") or "unknown",
        "exists": exists,
        "ready": exists,
        "size_bytes": path.stat().st_size if exists else 0,
        "byte_order": "",
        "tiff_version": None,
        "warnings": [],
    }
    if not exists:
        payload["warnings"].append("raster_missing")
        return payload

    if path.suffix.lower() not in (".tif", ".tiff"):
        payload["warnings"].append("raster_signature_not_checked")
        return payload

    with path.open("rb") as handle:
        header = handle.read(4)
    if len(header) < 4 or header[:2] not in (b"II", b"MM"):
        payload["ready"] = False
        payload["warnings"].append("invalid_tiff_header")
        return payload

    endian = "<" if header[:2] == b"II" else ">"
    payload["driver"] = "TIFF"
    payload["byte_order"] = "little" if endian == "<" else "big"
    payload["tiff_version"] = int(struct.unpack(f"{endian}H", header[2:4])[0])
    return payload


def _read_dbf_contract(path: Path):
    if not path.exists():
        return {
            "record_count": None,
            "field_count": None,
            "field_names": [],
        }

    with path.open("rb") as handle:
        header = handle.read(32)
        record_count = int(struct.unpack("<I", header[4:8])[0])
        header_length = int(struct.unpack("<H", header[8:10])[0])
        field_count = max(0, (header_length - 33) // 32)
        handle.seek(32)
        field_names = []
        for _ in range(field_count):
            field_descriptor = handle.read(32)
            raw_name = field_descriptor[:11].split(b"\x00", 1)[0]
            field_names.append(_decode_text(raw_name))
    return {
        "record_count": record_count,
        "field_count": field_count,
        "field_names": field_names,
    }


def inspect_vector(path: Path):
    path = path.expanduser().resolve()
    exists = path.exists()
    payload = {
        "path": str(path),
        "kind": "vector",
        "driver": path.suffix.lower().lstrip(".") or "unknown",
        "exists": exists,
        "ready": exists,
        "geometry_type": "",
        "record_count": None,
        "field_count": None,
        "field_names": [],
        "bbox": None,
        "crs_wkt": "",
        "encoding": "",
        "missing_files": [],
        "warnings": [],
    }
    if not exists:
        payload["warnings"].append("vector_missing")
        return payload

    if path.suffix.lower() != ".shp":
        payload["warnings"].append("vector_metadata_limited_without_gdal")
        return payload

    payload["driver"] = "ESRI Shapefile"
    missing_files = missing_shapefile_sidecars(path)
    payload["missing_files"] = missing_files
    payload["ready"] = not missing_files

    with path.open("rb") as handle:
        header = handle.read(100)
    shape_type = int(struct.unpack("<i", header[32:36])[0])
    bbox = struct.unpack("<4d", header[36:68])
    payload["geometry_type"] = SHAPE_TYPE_NAMES.get(shape_type, f"Unknown({shape_type})")
    payload["bbox"] = [float(value) for value in bbox]

    dbf_contract = _read_dbf_contract(path.with_suffix(".dbf"))
    payload["record_count"] = dbf_contract["record_count"]
    payload["field_count"] = dbf_contract["field_count"]
    payload["field_names"] = dbf_contract["field_names"]

    prj_path = path.with_suffix(".prj")
    if prj_path.exists():
        payload["crs_wkt"] = prj_path.read_text(encoding="utf-8", errors="ignore").strip()
    cpg_path = path.with_suffix(".cpg")
    if cpg_path.exists():
        payload["encoding"] = cpg_path.read_text(encoding="utf-8", errors="ignore").strip()

    if payload["geometry_type"].startswith("Polygon"):
        payload["warnings"].append("polygon_sites_use_centroid_in_analysis")
    if payload["record_count"] is not None and payload["record_count"] < 3:
        payload["warnings"].append("too_few_features_for_calibration")
    if missing_files:
        payload["warnings"].append("incomplete_shapefile_bundle")
    return payload


def build_case_payload(
    *,
    case_id: str,
    title: str,
    dem_relpath: str,
    sites_relpath: str,
    water_relpath: str = "",
    profile: str = "tomb",
    culture_key: str = "",
    period_key: str = "",
    hemisphere: str = "north",
    auto_hydro: bool = False,
    audience: str = "researcher_beta",
    truth_level: str = "site_level",
    positive_definition: str = "",
    negative_definition: str = "",
    water_policy: str = "",
    interpretation_boundary: str = "",
    score_drift_tolerance: float = 0.05,
):
    inputs = {
        "dem": dem_relpath,
        "sites": sites_relpath,
    }
    if water_relpath:
        inputs["water"] = water_relpath
    neutral_run = {
        "profile": profile,
        "culture_key": "",
        "period_key": "",
        "hemisphere": hemisphere,
        "auto_hydro": bool(auto_hydro),
        "context_enabled": False,
    }
    context_run = {
        "profile": profile,
        "culture_key": culture_key,
        "period_key": period_key,
        "hemisphere": hemisphere,
        "auto_hydro": bool(auto_hydro),
        "context_enabled": True,
    }
    calibrated_run = dict(context_run)
    calibrated_run["calibration_mode"] = "local"

    profile_text = str(profile or "").strip()
    if not positive_definition:
        positive_definition = (
            "polygon_centroid_clusters"
            if truth_level == "cluster_level"
            else "site_layer_features"
        )
    if not negative_definition:
        negative_definition = (
            "same_aoi_non_tomb_controls"
            if profile_text.startswith("tomb")
            else "same_aoi_non_site_controls"
        )
    if not water_policy:
        water_policy = "auto_hydro_only" if auto_hydro else "supplied_water"
    if not interpretation_boundary:
        interpretation_boundary = (
            "not_individual_tomb_detection"
            if truth_level == "cluster_level"
            else "descriptive_site_level_interpretation"
        )

    limitations = []
    if truth_level == "cluster_level":
        limitations.append("polygon_sites_centroid_cluster_level_only")
    if auto_hydro:
        limitations.append("auto_hydro_only")
    limitations.append("descriptive_only_until_held_out_split")

    return {
        "case_id": case_id,
        "title": title,
        "workflow": ["analysis", "compare", "calibration"],
        "inputs": inputs,
        "run_defaults": {
            "profile": profile,
            "culture_key": culture_key,
            "period_key": period_key,
            "hemisphere": hemisphere,
            "auto_hydro": bool(auto_hydro),
        },
        "benchmark": {
            "mode": "descriptive_benchmark",
            "audience": audience,
            "truth_level": truth_level,
            "positive_definition": positive_definition,
            "negative_definition": negative_definition,
            "water_policy": water_policy,
            "interpretation_boundary": interpretation_boundary,
            "run_matrix": {
                "neutral": neutral_run,
                "context": context_run,
                "calibrated": calibrated_run,
            },
            "compare_pairs": list(_STANDARD_COMPARE_PAIRS),
            "limitations": limitations,
        },
        "expected": {
            "required_artifacts": dict(_STANDARD_REQUIRED_ARTIFACTS),
            "compare_pairs": list(_STANDARD_COMPARE_PAIRS),
        },
        "score_drift_tolerance": float(score_drift_tolerance),
    }


def _benchmark_note_template(*, case_payload: dict, note_kind: str):
    benchmark = case_payload.get("benchmark", {})
    compare_pairs = benchmark.get("compare_pairs", [])
    kind_label = "False Positive" if note_kind == "false_positive" else "False Negative"
    lines = [
        f"# {kind_label} Notes",
        "",
        f"- Case: {case_payload.get('case_id', 'unknown')}",
        f"- Benchmark mode: {benchmark.get('mode', 'descriptive_benchmark')}",
        f"- Truth level: {benchmark.get('truth_level', 'unknown')}",
        f"- Water policy: {benchmark.get('water_policy', 'unspecified')}",
        "",
        "## Taxonomy",
        "- DEM quality / preservation issue",
        "- hydro sourcing issue",
        "- parameter oversensitivity",
        "- literature-to-terrain mismatch",
        "",
        "## Runs Reviewed",
    ]
    if compare_pairs:
        for pair in compare_pairs:
            lines.append(f"- {pair.get('id', '')}")
    else:
        lines.append("- neutral")
    lines.extend(
        [
            "",
            "## Notes",
            "- Add one short entry per mismatch.",
            "- Mark calibration interpretations as descriptive only until a held-out split exists.",
            "- If the issue comes from polygon centroid proxies or auto-hydro fallback, say so explicitly.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_if_missing(path: Path, text: str):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _case_readme_text(*, case_payload: dict, warnings: list[str], inspections: dict, qgis_available: bool):
    benchmark = case_payload.get("benchmark", {})
    expected = case_payload.get("expected", {})
    run_matrix = benchmark.get("run_matrix", {})
    compare_pairs = expected.get("compare_pairs", [])
    required_artifacts = expected.get("required_artifacts", {})
    lines = [
        f"# {case_payload['title']}",
        "",
        "## Inputs",
        f"- DEM: {case_payload['inputs']['dem']}",
        f"- Sites: {case_payload['inputs']['sites']}",
    ]
    if "water" in case_payload["inputs"]:
        lines.append(f"- Water: {case_payload['inputs']['water']}")
    else:
        lines.append("- Water: not provided (plan to use DEM auto-hydro)")

    lines.extend(
        [
            "",
            "## Runtime",
            f"- QGIS runtime available here: {'yes' if qgis_available else 'no'}",
            "",
            "## Benchmark Defaults",
            f"- Mode: {benchmark.get('mode', 'descriptive_benchmark')}",
            f"- Audience: {benchmark.get('audience', 'researcher_beta')}",
            f"- Truth level: {benchmark.get('truth_level', 'unknown')}",
            f"- Water policy: {benchmark.get('water_policy', 'unspecified')}",
            f"- Interpretation boundary: {benchmark.get('interpretation_boundary', 'unspecified')}",
            "",
            "## Standard Run Matrix",
            "- neutral: "
            f"profile={run_matrix.get('neutral', {}).get('profile', '')}, "
            "context=off",
            "- context: "
            f"profile={run_matrix.get('context', {}).get('profile', '')}, "
            f"culture={run_matrix.get('context', {}).get('culture_key', '') or 'unset'}, "
            f"period={run_matrix.get('context', {}).get('period_key', '') or 'unset'}",
            "- calibrated: "
            f"profile={run_matrix.get('calibrated', {}).get('profile', '')}, "
            f"culture={run_matrix.get('calibrated', {}).get('culture_key', '') or 'unset'}, "
            f"period={run_matrix.get('calibrated', {}).get('period_key', '') or 'unset'}, "
            "calibration=local",
            "",
            "## Fixed Compare Pairs",
        ]
    )
    if compare_pairs:
        for pair in compare_pairs:
            lines.append(
                f"- {pair.get('id', '')}: {pair.get('candidate', '')} vs {pair.get('base', '')}"
            )
    else:
        lines.append("- no compare pairs")

    lines.extend(
        [
            "",
            "## Required Artifacts",
        ]
    )
    if required_artifacts:
        for artifact_key, artifact_path in required_artifacts.items():
            lines.append(f"- {artifact_key}: {artifact_path}")
    else:
        lines.append("- no artifact contract")

    lines.extend(
        [
            "",
            "## Notes",
        ]
    )
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- no warnings")

    lines.extend(
        [
            "",
            "## Inspections",
            f"- Site geometry: {inspections['sites'].get('geometry_type') or 'unknown'}",
            f"- Site features: {inspections['sites'].get('record_count')}",
            f"- Site encoding: {inspections['sites'].get('encoding') or 'unknown'}",
            f"- Score drift tolerance: {case_payload.get('score_drift_tolerance')}",
            "",
            "## Suggested next steps",
            "- Preserve the neutral -> context -> calibrated sequence for the first descriptive benchmark pass.",
            "- Generate a reproducibility manifest with tools/build_repro_manifest.py.",
            "- Build a benchmark manifest with tools/build_benchmark_manifest.py after each preserved run.",
            "- If QGIS is installed later, run the same case with the frozen inputs in this folder.",
            "- If the sites layer is polygon-based, treat current outputs as cluster-level only until a representative point layer exists.",
        ]
    )
    return "\n".join(lines) + "\n"


def setup_study_case(
    *,
    case_dir: Path,
    dem: Path,
    sites: Path,
    water: Path | None = None,
    title: str = "",
    profile: str = "tomb",
    culture_key: str = "",
    period_key: str = "",
    hemisphere: str = "north",
):
    case_dir = case_dir.expanduser().resolve()
    dem = _ensure_file(dem, "dem")
    sites = _ensure_file(sites, "sites")
    water = _ensure_file(water, "water") if water else None

    inputs_dir = case_dir / "inputs"
    reports_dir = case_dir / "reports"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    dem_dst = inputs_dir / f"study_dem{dem.suffix.lower()}"
    sites_dst = inputs_dir / f"study_sites{sites.suffix.lower()}"
    water_dst = inputs_dir / f"study_water{water.suffix.lower()}" if water else None

    copy_with_sidecar(dem, dem_dst)
    copy_with_sidecar(sites, sites_dst)
    if water and water_dst:
        copy_with_sidecar(water, water_dst)

    inspections = {
        "dem": inspect_raster(dem_dst),
        "sites": inspect_vector(sites_dst),
    }
    if water_dst:
        inspections["water"] = inspect_vector(water_dst)

    qgis_available = qgis_runtime_available()
    warnings = []
    if inspections["sites"].get("geometry_type", "").startswith("Polygon"):
        warnings.append(
            "sites layer is polygon-based; current analysis treats each polygon via centroid, so results are cluster-level rather than tomb-level"
        )
    if not qgis_available:
        warnings.append(
            "QGIS runtime is not installed in this shell yet; this environment can prepare and inspect cases, but cannot execute the plugin headlessly"
        )
    if not water_dst:
        warnings.append("water layer was not provided; any full run should document DEM auto-hydro usage")

    case_id = case_dir.name
    case_payload = build_case_payload(
        case_id=case_id,
        title=title or case_id.replace("_", " "),
        dem_relpath=str(dem_dst.relative_to(case_dir)),
        sites_relpath=str(sites_dst.relative_to(case_dir)),
        water_relpath=str(water_dst.relative_to(case_dir)) if water_dst else "",
        profile=profile,
        culture_key=culture_key,
        period_key=period_key,
        hemisphere=hemisphere,
        auto_hydro=water_dst is None,
        truth_level=(
            "cluster_level"
            if inspections["sites"].get("geometry_type", "").startswith("Polygon")
            else "site_level"
        ),
        positive_definition=(
            "polygon_centroid_clusters"
            if inspections["sites"].get("geometry_type", "").startswith("Polygon")
            else "site_layer_features"
        ),
    )
    case_json_path = case_dir / "case.json"
    case_json_path.write_text(
        json.dumps(case_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    readme_path = case_dir / "README.md"
    readme_path.write_text(
        _case_readme_text(
            case_payload=case_payload,
            warnings=warnings,
            inspections=inspections,
            qgis_available=qgis_available,
        ),
        encoding="utf-8",
    )

    required_artifacts = case_payload.get("expected", {}).get("required_artifacts", {})
    false_positive_path = case_dir / required_artifacts.get(
        "false_positive_notes", "reports/false_positive_notes.md"
    )
    false_negative_path = case_dir / required_artifacts.get(
        "false_negative_notes", "reports/false_negative_notes.md"
    )
    _write_if_missing(
        false_positive_path,
        _benchmark_note_template(case_payload=case_payload, note_kind="false_positive"),
    )
    _write_if_missing(
        false_negative_path,
        _benchmark_note_template(case_payload=case_payload, note_kind="false_negative"),
    )

    return {
        "ok": True,
        "case_dir": str(case_dir),
        "case_json": str(case_json_path),
        "readme_path": str(readme_path),
        "inputs": case_payload["inputs"],
        "run_defaults": case_payload["run_defaults"],
        "analysis_ready": bool(inspections["dem"]["ready"] and inspections["sites"]["ready"]),
        "qgis_available": qgis_available,
        "warnings": warnings,
        "inspections": inspections,
    }
