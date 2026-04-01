# Troubleshooting

Updated: 2026-04-01

## CRS warning or unreliable distance behavior

Cause:

- DEM or project CRS is geographic

What to do:

- reproject to a meter-based CRS
- rerun extraction and analysis

## Auto-hydro looks strange

Cause:

- DEM artifacts
- flat terrain
- missing curated water input

What to do:

- prefer a curated water layer
- inspect DEM quality
- mark the run as exploratory

## Calibration finished but should not be overtrusted

Check:

- whether held-out evaluation rows existed
- whether the context is exploratory
- whether the selected profile is locally calibrated

Remember:

- calibration is tuning plus reportable evaluation metadata
- it is not a universal validation result

## Compare says gain/drop

Meaning:

- scores changed relative to the selected base profile

It does not mean:

- the calibrated profile is historically correct
- the plugin has proven site presence

## Need help from maintainers

Use the `Export Support Bundle` action first, then attach the generated zip to a bug report.
