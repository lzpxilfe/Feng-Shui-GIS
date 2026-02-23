# Feng Shui GIS (QGIS Plugin) v0.1.0

Feng Shui GIS is a DEM-first interpretation plugin for archaeology-oriented landscape reading.

## What It Does

1. Extracts ridge hierarchy from DEM (`daegan`, `jeongmaek`, `gimaek`, `jimaek`).
2. Extracts hydro network from DEM (if no water layer is supplied).
3. Optionally derives Feng Shui term points and structural links.
4. Optionally scores candidate sites (`fs_score`) when point data is provided.

## Core Principle

- Base mode is terrain-flow interpretation from DEM + hydro.
- Site scoring and detailed term network are optional, not mandatory.

## Outputs

- `*_fengshui_ridges`
- `*_fengshui_hydro`
- `*_fengshui_terms` (optional)
- `*_fengshui_terms_links` (optional)
- `*_fengshui` (optional site scoring)

## Interpretability

- Layers expose `reason_ko` / `fs_reason` fields.
- Selecting a feature shows reasoning text in QGIS message bar.
- Map tip templates include key metrics for each layer type.

## Configuration (No Hardcoded Research Constants)

- `feng_shui_gis/config/contexts.json`
- `feng_shui_gis/config/profiles.json`
- `feng_shui_gis/config/terms.json`
- `feng_shui_gis/config/analysis_rules.json`

## Evidence and Limits

Use these docs before research publication:

- `docs/reference_audit.md`
- `docs/research_matrix.md`
- `docs/regional_period_notes.md`
- `docs/context_profiles.md`

Important:
- DEM/ridge/hydro extraction is reproducible.
- Country/period context biases are still hypothesis priors and require local calibration.

## Quick Start

1. Load plugin in QGIS.
2. Select DEM.
3. Run `Extract Landscape Flow / Maek`.
4. Optionally enable term extraction.
5. Optionally run site scoring if you have point data.

## Recommended Data Conditions

- Projected CRS in meters (UTM/TM recommended).
- DEM quality strongly affects ridge/hydro/term outputs.

## Disclaimer

This plugin is a research support tool. Automated output is not a final archaeological conclusion.
Ground-truth validation is required.
