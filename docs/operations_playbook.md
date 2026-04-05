# Operations Playbook

Updated: 2026-04-01

This document defines the minimum operating standard for repeatable Feng Shui GIS runs.

## 1. Scope

The goal is not to claim universal speed. The goal is to make each run auditable:

- what was executed
- which artifact set was archived
- what budget tier was used
- whether cancel/progress behavior stayed within expectation

## 2. Benchmark Tiers

Use the same tier language across notes, reports, and review:

- `small`: one localized study area, minimal candidate points, quick iteration
- `medium`: one normal research case with scoring or compare enabled
- `large`: dense site inventory, calibration or repeated compare/export workflow

Start from [performance_budget.template.json](../examples/performance_budget.template.json) and adapt the thresholds to your machine or lab standard.

## 3. Required Artifacts

For any run you want to preserve or compare later, archive:

- reproducibility manifest
- benchmark manifest
- report JSON / Markdown
- exported layer names or stable paths
- notes about manual preprocessing

## 4. Headless / CI-Friendly Record

Successful QGIS UI workflows now auto-save:

- `reports/feng_shui_run_<service>_<run_id>.json`
- `reports/feng_shui_benchmark_<service>_<run_id>.json`

After a run finishes, build a benchmark manifest:

```bash
python3 tools/build_benchmark_manifest.py \
  --dataset-id my-study-001 \
  --service analysis \
  --benchmark-tier medium \
  --qgis-version 3.40.5 \
  --runtime-seconds 21.4 \
  --peak-memory-mb 640 \
  --cancel-latency-ms 900 \
  --manifest reports/repro_manifest.json \
  --report reports/feng_shui_compare_20260401_120000.json \
  --markdown reports/feng_shui_compare_20260401_120000.md \
  --output reports/benchmark_manifest.json
```

This keeps the archive step machine-readable even when the original run was triggered from the QGIS UI.

When the run belongs to a frozen study case, prefer the case-folder path:

```bash
python3 tools/build_benchmark_manifest.py \
  --case-dir /path/to/gongju_baekje_case \
  --service analysis \
  --benchmark-tier medium \
  --qgis-version 3.40.5 \
  --runtime-seconds 21.4 \
  --peak-memory-mb 640 \
  --cancel-latency-ms 900
```

`--case-dir` reads `case.json` and carries over the study-case contract:

- workflow steps
- score drift tolerance
- descriptive benchmark metadata
- expected artifact contract

For the current Gongju researcher-beta benchmark, preserve the same sequence every time:

1. neutral
2. context
3. calibrated
4. `context_vs_neutral`
5. `calibrated_vs_context`

## 5. Progress / Cancel Expectations

During long operations:

- the active action should be visible in the dock
- the cancel button should be enabled only while work is running
- the workflow guide should show a running-specific status, not stale setup guidance

## 6. Review Checklist

Before accepting a benchmark or report bundle:

- the `run_manifest` or reproducibility manifest is present
- the benchmark tier is declared
- runtime and peak-memory fields are filled
- cancellation latency is recorded when the workflow was interruptible
- report and markdown artifacts are hashed in the benchmark manifest
