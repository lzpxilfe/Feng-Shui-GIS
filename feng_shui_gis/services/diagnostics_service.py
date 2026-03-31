# -*- coding: utf-8 -*-
"""Diagnostic-only services used by UI and orchestration layers."""

from ..analysis import FengShuiAnalyzer
from ..service_contracts import DemDiagnosticsRequest, DemDiagnosticsOutput


class FengShuiDiagnosticService:
    @staticmethod
    def run_dem_diagnostics(
        request: DemDiagnosticsRequest,
    ) -> DemDiagnosticsOutput:
        diagnostics = FengShuiAnalyzer.adaptive_spacing_diagnostics(
            request.dem_layer,
            request.dem_step,
        )
        return DemDiagnosticsOutput(
            dem_step=float(diagnostics["dem_step"]),
            width=float(diagnostics["width"]),
            height=float(diagnostics["height"]),
            spacing=float(diagnostics["spacing"]),
            approx_nodes=int(diagnostics["approx_nodes"]),
            max_points=int(diagnostics["max_points"]),
        )
