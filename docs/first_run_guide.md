# First Run Guide

Updated: 2026-04-01

This guide is the shortest path for a first-time researcher using Feng-Shui-GIS.

## 1. Start with the sample project

Use [examples/sample_project/README.md](/Users/hwangjinseo/Desktop/Coding/Feng%20Shui/examples/sample_project/README.md) first.

It gives you:

- a small synthetic DEM
- a simple water layer
- a small candidate point layer
- expected report examples

## 2. Minimum safe setup

1. Load the DEM.
2. Confirm the project CRS is projected in meters.
3. Load water and sites if available.
4. Open the plugin and stay in `Quick` or `Research`.
5. Run terrain extraction first.
6. Only then move to scoring, compare, or calibration.

## 3. Why projected CRS matters

Distance-based terrain logic is used throughout the plugin.

- If the DEM is in geographic degrees, radius and smoothing behavior become distorted.
- For reproducible interpretation, use a projected CRS in meters whenever possible.

## 4. DEM quality warnings

Low-quality DEMs can create misleading outputs:

- noisy ridges
- unstable water-distance behavior
- overconfident-looking score changes
- weak or fragmented term structure

If the DEM is coarse, treat outputs as exploratory.

## 5. Auto-hydro limitations

Auto-hydro is a fallback, not a replacement for curated hydrology.

- use a trusted water layer if you have one
- use auto-hydro when you need a fast first pass
- document when auto-hydro was used in your notes or support bundle

## 6. How not to read results

- `fs_score` is not the probability of site presence
- calibration is not a standalone validation claim
- compare gain/drop is not “better/worse in absolute terms”
- context presets can include heuristic priors and exploratory assumptions

Use the plugin as a comparative reading frame, not an oracle.
