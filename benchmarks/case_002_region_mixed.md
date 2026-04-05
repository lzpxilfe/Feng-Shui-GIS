# Case 002 — Region-mixed profile split

Version: 2026-04-04

## Context

- Region: mixed river-basin + upland fringe
- Period: late historic adaptation zone proxy
- Site type: `mixed` (tomb + habitation)
- DEM: 공개 수문 지형 DEM
- Water source: no-supplied scenario + auto-hydro baseline

## Hypothesis

region profile을 적용했을 때 context baseline 대비 context/neutral 성능 차이가 해석 가능한 범위에서 존재하는지.

## Inputs

- sites_positive: confirmed archeological points (coarse)
- sites_negative: same-study non-target points
- split_seed: 77
- negative ratio: 3
- include_terms: optional

## Expected checks

- bad CRS path documented when geographic CRS is used
- auto-hydro warning appears and run still proceeds where possible
- compare top-change includes same feature UID across base/compare

## Result tracking

- score_drift_tolerance: `0.06`
- false_negative_notes: fill
- false_positive_notes: fill
