# First Run Guide

Updated: 2026-04-01

This guide is the shortest path for a first-time researcher using Feng-Shui-GIS.

## 1. Start with the sample project

Use [examples/sample_project/README.md](../examples/sample_project/README.md) first.

It gives you:

- a small synthetic DEM
- a simple water layer
- a small candidate point layer
- expected report examples

## 2. Five-step first run

1. Load the DEM.
2. Select a water layer, or use auto-hydro if you do not have one.
3. Select the candidate point layer.
4. Run terrain extraction and then site analysis.
5. Check the result layers and the generated report artifacts.

## 3. Three common first runs

### Quick terrain reading

- start with DEM + water
- stay in `Quick`
- confirm ridge / hydro / first scoring outputs appear

### Research compare / calibration

- use the sample sites layer
- stay in `Research`
- run compare or calibration only after the first analysis path succeeds

### Support bundle repro sharing

- reproduce the issue once
- export a support bundle
- attach the bundle and report what the DEM / CRS / water setup looked like

## 4. Why projected CRS matters

Distance-based terrain logic is used throughout the plugin.

- If the DEM is in geographic degrees, radius and smoothing behavior become distorted.
- For reproducible interpretation, use a projected CRS in meters whenever possible.

## 5. DEM quality warnings

Low-quality DEMs can create misleading outputs:

- noisy ridges
- unstable water-distance behavior
- overconfident-looking score changes
- weak or fragmented term structure

If the DEM is coarse, treat outputs as exploratory.

## 6. Auto-hydro limitations

Auto-hydro is a fallback, not a replacement for curated hydrology.

- use a trusted water layer if you have one
- use auto-hydro when you need a fast first pass
- document when auto-hydro was used in your notes or support bundle

## 7. How not to read results

- `fs_score` is not the probability of site presence
- calibration is not a standalone validation claim
- compare gain/drop is not “better/worse in absolute terms”
- context presets can include heuristic priors and exploratory assumptions

Use the plugin as a comparative reading frame, not an oracle.
