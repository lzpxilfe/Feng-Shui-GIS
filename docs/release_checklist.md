# Release Checklist

Updated: 2026-04-01

## Metadata

- `metadata.txt` version/homepage/repository/tracker are correct
- `description` and `about` clearly say heuristic / not predictive / calibration limitation / projected CRS recommendation
- changelog text matches the release
- changelog mentions schema / profile / calibration logic changes when relevant

## Productization assets

- sample project files exist
- first-run guide exists
- troubleshooting guide exists
- support bundle guide exists
- bug report template exists
- tested versions / known limitations doc exists

## Functional checks

- plugin installs and enables
- dock opens without crashing
- sample project can be loaded
- sample project minimal path succeeds
- result report artifact exists
- support bundle export succeeds
- latest run/benchmark manifest generation still works
- asset smoke script completes
- headless smoke script completes

## Documentation

- README links are valid
- quickstart links are valid
- release note references are valid
- sample project README explains expected outputs
- known limitations are linked from README
