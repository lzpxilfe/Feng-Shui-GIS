# ⛰️ Feng Shui GIS for QGIS

> DEM-first terrain and water interpretation for Feng Shui-informed landscape analysis, archaeology support, and reproducible research workflows.

## ✨ What This Plugin Does

Feng Shui GIS is built around a simple idea: start from terrain and water first, then layer on optional interpretation.

- ⛰️ Extracts ridge hierarchy from DEMs (`daegan`, `jeongmaek`, `gimaek`, `jimaek`)
- 🌊 Uses a supplied water layer first, or derives a hydro network from DEM when needed
- 🧭 Optionally derives Feng Shui term points and structural links
- 📍 Optionally scores candidate sites with `fs_score`
- 🏷️ Optionally enriches outputs with nearby mountain names from OSM/Overpass
- 📚 Shows context evidence in the UI with source attribution (`source_doi`, `evidence_level`)
- 🧪 Runs SHP-based calibration and writes report outputs to `reports/*.json` and `reports/*.md`

## 🧠 Core Design

- Base mode is `DEM + water` landscape reading
- Advanced scoring and term extraction are optional layers on top
- Region and period settings are config-driven, not hardcoded into the UI
- The plugin is designed to support interpretation, not replace fieldwork or historical judgment

## 🆕 Current Feature Set

As of `v0.1.2`, the plugin includes:

- 🎛️ General-principles default mode for lower-friction landscape extraction
- 🌍 Optional advanced context toggle for culture/period-aware analysis
- 🏔️ OSM mountain-name enrichment with preferred language selection (`local` / `ko` / `en`)
- 🔎 Reason fields such as `reason_ko` and `fs_reason` on output layers
- 📖 Evidence dialogs and context parameter inspection in the UI
- 📏 Reproducibility-oriented config files under `feng_shui_gis/config/`

## 📦 Main Outputs

| Layer | Description |
|---|---|
| `*_fengshui_ridges` | Ridge hierarchy extracted from DEM |
| `*_fengshui_hydro` | Supplied or DEM-derived hydro network |
| `*_fengshui_terms` | Optional Feng Shui term points |
| `*_fengshui_links` | Optional structural link lines between terms |
| `*_fengshui` | Optional site scoring layer with `fs_score` and reasoning fields |

## 🖥️ Requirements

- QGIS `3.28+`
- A projected CRS in meters is strongly recommended
- DEM quality directly affects ridge, hydro, and term outputs

## 🚀 Quick Start

1. Load the plugin in QGIS.
2. Select a DEM raster.
3. Add a curated water layer if you have one.
4. If no water layer is available, enable DEM auto-hydro.
5. Run `Extract Landscape Flow / Maek`.
6. Turn on term extraction only when you need Feng Shui term geometry.
7. Run site scoring only when you have point data to evaluate.
8. If needed, enable mountain-name enrichment for presentation or inspection.

## 🔬 Researcher Workflow

If the goal is publication, validation, or sharing with other labs:

1. Freeze the plugin version and config snapshot before analysis.
2. Generate a manifest with `python3 tools/build_repro_manifest.py`.
3. Follow [docs/researcher_quickstart.md](docs/researcher_quickstart.md).
4. Use [docs/validation_protocol.md](docs/validation_protocol.md) before claiming replication or benchmark agreement.
5. Run `python3 -m unittest discover -s tests` for the repository's reproducibility contract checks.

## ⚙️ Config-Driven by Design

The main research parameters live in JSON config files:

- `feng_shui_gis/config/contexts.json`
- `feng_shui_gis/config/profiles.json`
- `feng_shui_gis/config/terms.json`
- `feng_shui_gis/config/analysis_rules.json`

This makes the plugin easier to audit, compare, and recalibrate across projects.

## 📚 Evidence, References, and Limits

Use these documents before research publication:

- [docs/reference_audit.md](docs/reference_audit.md)
- [docs/research_matrix.md](docs/research_matrix.md)
- [docs/regional_period_notes.md](docs/regional_period_notes.md)
- [docs/context_profiles.md](docs/context_profiles.md)
- [docs/researcher_quickstart.md](docs/researcher_quickstart.md)
- [docs/validation_protocol.md](docs/validation_protocol.md)

Important limits:

- ✅ DEM / ridge / hydro extraction is the most reproducible part of the stack
- ⚠️ Country and period context profiles are still research priors unless locally validated
- ⚠️ Automated output should not be presented as a final archaeological conclusion by itself

## 🧾 Reproducibility Support

This repository now includes:

- `examples/reproducibility_manifest.template.json`
- `tools/build_repro_manifest.py`
- `tests/test_reproducibility_contract.py`

These are intended to make it easier for researchers to archive runs, compare outputs, and share exact configuration states.

## ⚠️ Disclaimer

Feng Shui GIS is a research support tool.

It is useful for structured terrain interpretation, exploratory spatial comparison, and reproducible workflow design.
It is not a substitute for excavation evidence, local historical context, or field verification.
