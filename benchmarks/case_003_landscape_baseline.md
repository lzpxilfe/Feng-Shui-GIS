# Case 003 — Landscape-only baseline

Version: 2026-04-04

## Context

- Region: broad landscape sample AOI
- Period: context-agnostic baseline
- Site type: `landscape_candidate`
- DEM: synthetic/low-noise test DEM
- Water source: supplied channel network

## Hypothesis

site layer 없이도 terrain extraction·term extraction 자체는 안정적으로 동작해야 하며, 점수 단계는 오프셋 경고만으로 fail-closed해야 함.

## Inputs

- sites_positive: 없음 (analysis without sites for smoke subset)
- sites_negative: 없음
- calibration: optional skip when no target sample exists
- benchmark focus: smoke reproducibility, not site ranking

## Expected checks

- `analysis` 레이어 생성
- compare/calibration failure paths are explicit and fail-closed
- run manifest includes manifest keys and artifact path

## Result tracking

- score_drift_tolerance: `0.03`
- failure_notes: fill
