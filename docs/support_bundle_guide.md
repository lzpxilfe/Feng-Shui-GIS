# Support Bundle Guide

Updated: 2026-04-01

`Export Support Bundle` creates a zip file meant for debugging and reproducible support.

## Included

- plugin metadata
- current UI/config snapshot
- selected layer summaries
- current project layer summaries
- latest run manifest
- latest benchmark manifest
- latest report JSON / Markdown
- recent in-plugin error log records
- current config JSON files

## Not included by default

- raw DEM raster
- raw source vector datasets
- private or large external files

Instead, the bundle stores path/CRS/feature-count/fingerprint references for those inputs.

## Recommended support workflow

1. Reproduce the issue once.
2. Export the support bundle from `Developer` mode or the plugin menu.
3. Attach the zip to your bug report.
4. Add one sentence describing whether the run used auto-hydro, advanced context, or local calibration.
