# -*- coding: utf-8 -*-
from __future__ import annotations

from .locale import tr
from .ui_catalog import ui_text


def workflow_checks_state(
    *,
    mode_tab_index,
    goal_key,
    dem_ready,
    sites_ready,
    water_ready,
    analysis_auto_hydro,
    landscape_auto_hydro,
    include_terms,
):
    terms_ready = include_terms if goal_key in ("tomb", "house", "settlement") else True

    if mode_tab_index == 1:
        hydro_ready = water_ready or analysis_auto_hydro
        checks = [
            (ui_text("workflow_check_dem", default="Select DEM layer"), dem_ready),
            (
                ui_text("workflow_check_sites", default="Select candidate site layer"),
                sites_ready,
            ),
            (ui_text("workflow_check_hydro", default="Confirm hydro source"), hydro_ready),
            (
                ui_text("workflow_check_analysis_ready", default="Ready to run analysis"),
                dem_ready and sites_ready and hydro_ready,
            ),
        ]
        return tr("tab_analysis"), tr("run_button"), checks

    hydro_ready = water_ready or landscape_auto_hydro
    checks = [
        (ui_text("workflow_check_dem", default="Select DEM layer"), dem_ready),
        (ui_text("workflow_check_hydro", default="Confirm hydro source"), hydro_ready),
        (
            ui_text(
                "workflow_check_terms_recommended",
                default="Turn on term points for site-shape reading",
            )
            if goal_key in ("tomb", "house", "settlement")
            else ui_text(
                "workflow_check_terms_option",
                default="Check term point/link options",
            ),
            terms_ready,
        ),
        (
            ui_text("workflow_check_extract_ready", default="Ready to run extraction"),
            dem_ready and hydro_ready and terms_ready,
        ),
    ]
    return tr("tab_landscape"), tr("extract_landscape_button"), checks
