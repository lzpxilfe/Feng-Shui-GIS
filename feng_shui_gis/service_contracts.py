# -*- coding: utf-8 -*-
"""Shared request/response contracts for Feng-Shui analysis services."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AnalysisRequest:
    site_layer: Any
    dem_layer: Any
    water_layer: Any
    hemisphere: str
    profile_key: str
    culture_key: str
    period_key: str
    auto_hydro: bool = False


@dataclass(frozen=True)
class AnalysisOutput:
    analysis_layer: Any
    auto_hydro_layer: Optional[Any]
    used_water_layer: Any
    run_manifest: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class TermExtractionRequest:
    dem_layer: Any
    water_layer: Any
    hemisphere: str
    profile_key: str
    culture_key: str
    period_key: str
    auto_hydro: bool
    include_terms: bool


@dataclass(frozen=True)
class TermExtractionOutput:
    ridge_layer: Any
    hydro_layer: Optional[Any]
    terms_layer: Optional[Any]
    term_links_layer: Optional[Any]
    used_water_layer: Any
    run_manifest: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class CompareRequest:
    site_layer: Any
    dem_layer: Any
    water_layer: Any
    hemisphere: str
    base_profile_key: str
    compare_profile_key: str
    culture_key: str
    period_key: str
    auto_hydro: bool = False


@dataclass(frozen=True)
class CompareOutput:
    base_layer: Any
    compare_layer: Any
    auto_hydro_layer: Optional[Any]
    used_water_layer: Any
    run_manifest: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class CalibrationRequest:
    site_layer: Any
    dem_layer: Any
    water_layer: Any
    hemisphere: str
    profile_key: str
    culture_key: str
    period_key: str
    negative_ratio: int
    random_seed: int
    auto_hydro: bool = False


@dataclass(frozen=True)
class CalibrationOutput:
    calibrated_layer: Any
    report: Dict[str, Any]
    auto_hydro_layer: Optional[Any]
    used_water_layer: Any
    run_manifest: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class DemDiagnosticsRequest:
    dem_layer: Any
    dem_step: Optional[float] = None


@dataclass(frozen=True)
class DemDiagnosticsOutput:
    dem_step: float
    width: float
    height: float
    spacing: float
    approx_nodes: int
    max_points: int
