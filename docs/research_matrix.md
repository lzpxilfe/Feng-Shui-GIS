# Research Matrix (Rebuilt, DOI-verified)

Updated: 2026-02-23

This matrix separates direct quantitative evidence from contextual interpretation sources.

## A. Direct Spatial / GIS Evidence (higher confidence)

| Domain | Source | DOI / Link | What it supports |
|---|---|---|---|
| Tomb-site parameter extraction | Um (2009), IJGIS | https://doi.org/10.1080/13658810802055954 | Spatially prioritized Feng Shui parameter framing from tomb footprint |
| Remote sensing + GIS on Feng Shui woodland | Tung Fung & Marafa (2002), IGARSS | https://doi.org/10.1109/IGARSS.2002.1027144 | Landscape pattern mapping from imagery and GIS |
| Korean landscape ecology / bi-bo woodland | Whang & Lee (2006) | https://doi.org/10.1007/s11355-006-0014-8 | Terrain-water-vegetation logic in Korean context |
| Compass-based Korean village case | Kim (2016), Journal of Koreanology | https://doi.org/10.15299/jk.2016.8.60.203 | Orientation and settlement interpretation workflow |

## B. Regional Context Evidence (medium confidence)

| Region | Source | DOI / Link | What it supports |
|---|---|---|---|
| Ryukyu/Okinawa | Chen et al. (2008), Worldviews | https://doi.org/10.1163/156853508X276824 | Village landscape morphology shaped by Feng Shui practice |
| Ryukyu/Okinawa | Nakama & Chen (2011), Worldviews | https://doi.org/10.1163/156853511X577475 | Landscape and planting logic over time |
| Ryukyu/Okinawa | UFUG (2008) | https://doi.org/10.1016/j.ufug.2007.10.001 | House-embracing tree layout metrics |
| Korea (Joseon) | P'ungsu chapter (2017) | https://doi.org/10.1515/9781438468716-011 | Architecture-geomancy relation |
| Korea (Joseon) | P'ungsu chapter (2017) | https://doi.org/10.1515/9781438468716-009 | Water acquisition/management geomancy practices |

## C. Parameterization Status in Plugin

- DEM-derived ridge/hydro extraction: algorithmic geomorphometry (implemented, reproducible).
- Term geometry (hyeol/myeongdang/blue-dragon/white-tiger): rule-based heuristic from literature interpretation.
- Country/period context weights (`contexts.json`): initial hypothesis profile, not final calibrated model.

## D. Required Next Validation (for research-grade use)

1. Per-country/per-period ground-truth site dataset.
2. Out-of-sample evaluation (AUC/PR/F1) by site type (tomb, village, temple, well, etc.).
3. Sensitivity analysis for radius, threshold, directional targets.
4. Publish calibration sheet and uncertainty intervals with each release.
