# Sample Project

This folder contains a repository-safe synthetic starter package for first-time users.

## Files

- `sample_dem.asc`: small synthetic DEM
- `sample_water.geojson`: simple line water layer
- `sample_sites.geojson`: candidate point layer
- `expected_analysis_report.json`
- `expected_compare_report.json`
- `expected_calibration_report.md`
- `expected_analysis.svg`
- `expected_compare.svg`
- `expected_calibration.svg`

## Suggested first run

1. Load `sample_dem.asc`
2. Load `sample_water.geojson`
3. Load `sample_sites.geojson`
4. Open the plugin in `Research`
5. Run terrain extraction
6. Run analysis
7. Inspect compare/calibration outputs against the expected report examples

## What a normal first run should create

### Expected layers

- `풍수_산줄기` / `fengshui_ridges`
- `풍수_수계` / `fengshui_hydro`
- `풍수_입지평가` / `fengshui`

### Expected report examples to compare against

- `expected_analysis_report.json`
- `expected_compare_report.json`
- `expected_calibration_report.md`

### Visual comparison examples

- `expected_analysis.svg`
- `expected_compare.svg`
- `expected_calibration.svg`

## Why this project exists

- it gives new users a safe first run
- it gives maintainers a shared repro package
- it gives the smoke workflow a stable, lightweight target
