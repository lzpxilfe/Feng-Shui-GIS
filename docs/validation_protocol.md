# Validation Protocol

Updated: 2026-03-20

This protocol defines how to evaluate the plugin against published studies or local archaeological truth data without overstating agreement.

## 1. Freeze the Benchmark Inputs

For each benchmark case, record:

- Plugin version
- QGIS version
- Git commit if available
- SHA256 hashes for every file in `feng_shui_gis/config/*.json`
- DEM source, resolution, and CRS
- Water source type: supplied layer or DEM-derived hydro
- Site inventory source, inclusion criteria, and label date

Do not change config or preprocessing after metrics have been computed unless the benchmark is rerun from scratch.

## 2. Define the Benchmark Case

Each paper or field dataset should be represented as one case sheet containing:

- Region and period
- Site type: tomb, village, temple, well, house, or mixed
- Positive sample definition
- Negative sample definition
- Geographic study window
- Metrics to compare
- Acceptance threshold or qualitative expectation

Before adding a country or period split, compare the same case against the
neutral/general context. Keep the split only when it improves held-out
performance or the source study explicitly depends on that historical context.

## 3. Split the Work Correctly

- Use calibration only on a training split.
- Evaluate the final model on a held-out split or an external case study.
- If the source paper has no explicit split, document that the replication is descriptive rather than predictive.

## 4. Metrics to Report

At minimum, report:

- `AUC`
- `PR-AUC`
- `F1` at the chosen threshold
- Rank agreement for top candidate sites
- Orientation or aspect distribution if the study claims directional effects
- Term overlap only when the paper operationalizes those terms spatially

## 5. Failure Reporting Rules

Report mismatches directly. Do not hide them inside narrative text.

- If the study window had to be approximated, say so.
- If a water layer was unavailable and DEM auto-hydro was used, say so.
- If the plugin required local calibration to match the paper, report the delta from default config.
- If results are unstable under small threshold changes, include a sensitivity note.
- If present-day DEM or hydrography was compared against ancient tombs or settlement remains, report preservation uncertainty such as mound truncation, terracing, stream relocation, or modern earthworks.

## 6. Publication Checklist

Before claiming replication, verify all of the following:

1. The run manifest exists and matches the archived outputs.
2. The config snapshot is archived alongside the manuscript materials.
3. Calibration and evaluation data were not mixed.
4. The paper-specific preprocessing steps are described in plain language.
5. The limits of `country/period` priors are stated explicitly.
6. Non-matching results are documented, not discarded.

## 7. Recommended Deliverables

- One case sheet per benchmark
- One machine-readable run manifest per execution
- One summary table comparing paper vs plugin outputs
- One short narrative on why agreements or disagreements occurred
