# Researcher Quickstart

Updated: 2026-03-20

This guide is the shortest path to a reproducible run that another lab can inspect and rerun.

## 1. Preconditions

- QGIS `3.28+`
- Plugin version recorded from `feng_shui_gis/metadata.txt`
- Projected CRS in meters for DEM-driven analysis
- One DEM raster
- One water layer if available; otherwise document that DEM auto-hydro was used
- Optional site point layer for scoring or calibration

## 2. Freeze the Analysis State

Before opening QGIS, record the exact plugin/config state:

```bash
python3 tools/build_repro_manifest.py \
  --dataset-id my-study-001 \
  --qgis-version 3.40.5 \
  --dem data/raw/dem.tif \
  --water data/raw/water.gpkg \
  --sites data/raw/sites.gpkg \
  --crs EPSG:5186 \
  --culture-key korea \
  --period-key early_modern \
  --profile tomb \
  --random-seed 42 \
  --validation-ratio 0.2 \
  --split-seed 1234 \
  --validation-group cv_holdout \
  --include-terms \
  --output reports/repro_manifest.json
```

Archive the generated JSON with the study outputs.

## 3. Minimal Reproducible Run

1. Start QGIS and load the DEM.
2. Load the water layer if you have a curated hydro source.
3. Load a site layer only if you intend to score or calibrate.
4. Confirm the project CRS matches the projected study CRS.
5. Open `Feng Shui GIS`.
6. Select hemisphere, profile, culture, and period explicitly.
7. Run `Extract Landscape Flow / Maek`.
8. If scoring is needed, run the analysis step on the same frozen inputs.
9. If calibration is needed, save both `reports/*.json` and `reports/*.md`.

## 4. What to Archive

- Input DEM and any supplied water/site layers, or stable references to them
- `reports/repro_manifest.json`
- A copy of `feng_shui_gis/config/*.json` used for the run
- Output layers (`*_fengshui_ridges`, `*_fengshui_hydro`, optional term/link/score layers)
- Calibration reports if calibration was run
- A short notes file describing any manual preprocessing outside the plugin

## 5. Interpretation Boundaries

Use the output as a transparent spatial aid, not as a final historical conclusion.

- DEM/ridge/hydro extraction is the most reproducible part of the stack.
- Context profiles in `contexts.json` remain research priors unless locally validated.
- Publication-grade claims should cite:
  - `docs/research_matrix.md`
  - `docs/reference_audit.md`
  - `docs/regional_period_notes.md`
  - `docs/validation_protocol.md`
