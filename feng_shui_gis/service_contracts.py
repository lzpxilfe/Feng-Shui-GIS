# -*- coding: utf-8 -*-
"""Shared request/response contracts for the next service-layer refactor.

These contracts are intentionally minimal and side-effect free:
- immutable request descriptors
- explicit output/metric envelopes
- lightweight manifest helpers for reproducibility
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha1
from time import time
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RunManifest:
    """Run-time manifest for reproducibility and auditability."""

    run_id: str
    service_name: str
    manifest_version: str
    config_sha: Optional[str]
    seed: Optional[int]
    qgis_version: Optional[str]
    qgis_info: Dict[str, Any]
    source_layers: Dict[str, str]
    started_at_unix: float

    @classmethod
    def for_service(
        cls,
        service_name: str,
        config_payload: Optional[Dict[str, Any]],
        seed: Optional[int],
        qgis_version: Optional[str],
        source_layers: Optional[Dict[str, str]],
    ) -> "RunManifest":
        qgis_info = {
            "qgis_version": qgis_version,
            "service": service_name,
            "python": "3.8+",
        }
        payload_bytes = str(config_payload or {}).encode("utf-8")
        config_sha = sha1(payload_bytes).hexdigest()
        run_id = sha1(
            f"{service_name}|{config_sha}|{seed}|{time()}".encode("utf-8")
        ).hexdigest()[:12]
        return cls(
            run_id=run_id,
            service_name=service_name,
            manifest_version="1.0.0",
            config_sha=config_sha,
            seed=seed,
            qgis_version=qgis_version,
            qgis_info=qgis_info,
            source_layers=source_layers or {},
            started_at_unix=time(),
        )

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnalysisRequest:
    site_layer: Any
    dem_layer: Any
    water_layer: Optional[Any]
    hemisphere: str
    profile_key: str
    culture_key: str
    period_key: str
    auto_hydro: bool = True
    label_language: str = "ko"
    negative_ratio: Optional[int] = None
    random_seed: Optional[int] = None
    mountain_options: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class AnalysisOutput:
    manifest: RunManifest
    site_layer_name: str
    profile_key: str
    context: Dict[str, str]
    base_layer_name: str
    report: Dict[str, Any]
    score_stats: Dict[str, Any]
    warnings: List[str]
    payloads: Dict[str, Any]


@dataclass(frozen=True)
class CompareRequest:
    site_layer: Any
    dem_layer: Any
    water_layer: Optional[Any]
    hemisphere: str
    base_profile_key: str
    compare_profile_key: str
    culture_key: str
    period_key: str
    auto_hydro: bool = True
    label_language: str = "ko"


@dataclass(frozen=True)
class ComparisonOutput:
    manifest: RunManifest
    site_layer_name: str
    base_profile_key: str
    compare_profile_key: str
    context: Dict[str, str]
    base_layer_name: str
    compare_layer_name: str
    top_changes: List[Dict[str, Any]]
    selected_change_uids: List[str]
    score_stats: Dict[str, Any]
    reports: Dict[str, Any]


@dataclass(frozen=True)
class CalibrationRequest:
    site_layer: Any
    dem_layer: Any
    water_layer: Optional[Any]
    hemisphere: str
    profile_key: str
    culture_key: str
    period_key: str
    negative_ratio: int = 3
    random_seed: int = 42
    auto_hydro: bool = True
    label_language: str = "ko"
    mountain_options: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class CalibrationOutput:
    manifest: RunManifest
    site_layer_name: str
    profile_key: str
    context: Dict[str, str]
    calibrated_layer_name: str
    calibration_fit: Dict[str, Any]
    calibration_report: Dict[str, Any]
    calibration_applied: bool
    evaluation_enabled: bool
    evaluation_base_metrics: Dict[str, Any]
    fit_metrics: Dict[str, Any]
    evaluation_metrics: Dict[str, Any]


@dataclass(frozen=True)
class TermExtractionRequest:
    dem_layer: Any
    water_layer: Optional[Any]
    hemisphere: str
    profile_key: str
    culture_key: str
    period_key: str
    auto_hydro: bool = True
    include_terms: bool = True
    label_language: str = "ko"
    mountain_options: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class TermExtractionOutput:
    manifest: RunManifest
    context: Dict[str, str]
    term_layer_names: List[str]
    field_layer_names: List[str]
    link_layer_names: List[str]
    metrics: Dict[str, Any]
    report: Dict[str, Any]
