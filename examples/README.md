# Examples

This directory contains reproducibility templates, not bundled research data.

Sample rasters and archaeological site inventories are intentionally not committed here because licensing, coordinate systems, and publication rights vary by study.

## Recommended Package Layout

Use a study bundle shaped like this:

```text
my-study/
  data/
    raw/
      dem.tif
      water.gpkg
      sites.gpkg
    derived/
  outputs/
    landscape/
    scoring/
  reports/
    repro_manifest.json
    calibration_report.json
    calibration_report.md
  config_snapshot/
    analysis_rules.json
    contexts.json
    profiles.json
    references.json
    terms.json
    ui_texts.json
  notes/
    preprocessing.md
```

Start from `reproducibility_manifest.template.json` and replace placeholders before the first run.

`performance_budget.template.json` is a companion template for defining small/medium/large runtime budgets before you start comparing benchmark records.
