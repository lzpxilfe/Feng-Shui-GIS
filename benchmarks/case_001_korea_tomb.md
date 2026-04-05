# Case 001 — Baekje Gongju tomb cluster (migration-site proxy)

Version: 2026-04-04

## Context

- Region: South Chungcheong Province, Gongju area (historic Baekje capital relocation context)
- Period: Baekje transitional relocation context
- Site type: `tomb_cluster` (known 고분군 points)
- DEM: provided sample DEM (`666.tif`) converted to projected CRS workflow
- Water source: supplied vector (high-level hydro support by hand-prepared synthetic source)

## Hypothesis

neutral profile이 기준이며, local context profile이 고분군 후보군에서 정렬/개선 효과를 보이는지 확인.

## Inputs

- sites_positive: supplied Baekje Gongju tomb points (`고분군.shp`)
- sites_negative: nearby non-tomb controls (to be curated in follow-up pass)
- neutral_window: study AOI polygon
- seed: 42
- validation ratio: 0.2

## Expected checks

- `run` / `analysis` layer 생성
- `compare` top-change drift exists and is interpretable
- calibration split disabled when data is insufficient -> `no_held_out_evaluation` 메시지 노출

## Result tracking

- score_drift_tolerance: `0.05`
- false_negative_notes: fill
- false_positive_notes: fill
