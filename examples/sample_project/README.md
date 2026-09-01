# 🧪 Sample Project

This folder is the starting point for repeatable regression-style walkthroughs.

## Included assets

- `sample_project.qgs`: lightweight QGIS project shell for the sample workflow
- relative layer placeholders that mirror the expected `DEM + water + sites` layout
- matching fixture contracts under `tests/fixtures/`

## Intended workflow

1. Open `sample_project.qgs` in QGIS.
2. Replace placeholder layer paths with your local synthetic or public sample inputs.
3. Run:
   - `analysis`
   - `compare`
   - `calibration`
4. Archive the resulting report/manifest artifacts for regression comparison.

## Expected layers

- `*_fengshui_ridges`
- `*_fengshui_hydro`
- `*_fengshui_terms`
- `*_fengshui_links`
- `*_fengshui`

## Expected report examples

- analysis report JSON / Markdown
- compare summary report
- calibration report
- run manifest
- benchmark manifest

## Notes

- This repository keeps the sample project lightweight and license-safe.
- Raw DEM/vector files are intentionally not bundled here yet.
- The regression contract lives in the fixture metadata and smoke scripts, not only in screenshots.
