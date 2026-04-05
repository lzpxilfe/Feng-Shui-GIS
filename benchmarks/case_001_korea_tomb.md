# Case 001 — Gongju Baekje tomb cluster

Version: 2026-04-06

## Status

- Canonical researcher-beta benchmark for the first real-data pass
- Benchmark mode: `descriptive_benchmark`
- Truth level: `cluster-level`
- Audience: `researcher_beta`

## Fixed Case Definition

- Region: Gongju area, South Chungcheong Province
- Period/context baseline: `korea + ancient`
- Profile baseline: `tomb`
- Hemisphere: `north`
- Positives: polygon centroid representation of the supplied Baekje tomb-cluster layer
- Negatives: non-tomb controls from the same AOI
- Water policy: `auto-hydro only`
- Interpretation boundary: current outputs are not individual tomb detection; they are cluster-level descriptive benchmark results

## Why This Case Exists

This case is the first locked real-data benchmark for Feng-Shui-GIS.
Its job is not to prove universal accuracy. Its job is to show whether:

- the neutral baseline is reproducible
- the `korea + ancient` context changes ranking in an interpretable way
- local calibration improves or merely overfits
- false positives and false negatives can be recorded without hand-waving

## Standard Run Matrix

1. `neutral`
   profile=`tomb`, context disabled, auto-hydro enabled
2. `context`
   profile=`tomb`, culture=`korea`, period=`ancient`, auto-hydro enabled
3. `calibrated`
   local calibration starting from the context run, auto-hydro enabled

## Fixed Compare Outputs

- `context_vs_neutral`
- `calibrated_vs_context`

Both compare outputs must be archived alongside the base analysis/calibration artifacts.

## Required Preserved Artifacts

- run manifest
- benchmark manifest
- analysis report
- compare summary
- calibration report
- false positive notes
- false negative notes
- score drift tolerance record

## Reporting Rules

- Use `descriptive benchmark` as the default label in notes and reports
- Only call the result predictive or held-out validation when a real split exists
- If calibration cannot support a held-out split, mark the calibration result as `descriptive only`
- Record false positives and false negatives with a small taxonomy:
  - DEM quality / preservation issue
  - hydro sourcing issue
  - parameter oversensitivity
  - literature-to-terrain mismatch

## Known Limits

- Point truth is not available yet
- The site layer is polygon-based, so the current truth proxy is centroid-driven
- Auto-hydro can shift local water evidence compared with a curated river layer
- This case should be used to lock benchmark discipline before broader tuning
