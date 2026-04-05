# 🧭 Feng Shui GIS

> **DEM-first QGIS plugin for terrain reading, principle-first Feng Shui interpretation, and comparative historical landscape analysis.**

이 저장소는 풍수를 "자동 정답기"로 만들기보다,  
`지형 구조 추출 -> 원리 기반 해석 -> 비교/보정 -> 반복 가능한 실험`의 흐름으로 다루기 위한 GIS 도구입니다.

![QGIS](https://img.shields.io/badge/QGIS-3.28%2B-589632?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat-square)
![Model](https://img.shields.io/badge/Model-Principle--first-7A5C3E?style=flat-square)
![Visualization](https://img.shields.io/badge/Visualization-Embodied%20terrain-1F6F78?style=flat-square)

---

## Start Here

| What you need | Where to go |
| --- | --- |
| Fast first run | [docs/first_run_guide.md](docs/first_run_guide.md) |
| Principle-first interpretation model | [docs/PRINCIPLES.md](docs/PRINCIPLES.md) |
| Visualization direction | [docs/VISUALIZATION.md](docs/VISUALIZATION.md) |
| Research workflow | [docs/researcher_quickstart.md](docs/researcher_quickstart.md) |
| Validation guidance | [docs/validation_protocol.md](docs/validation_protocol.md) |

---

## What This Plugin Does

### 1. Terrain structure first

- extracts ridge hierarchy from DEM
- accepts a supplied water layer or derives hydro from DEM
- builds terrain metrics needed for later interpretation

### 2. Principle-first Feng Shui reading

Site scoring is no longer framed as "the profile says tomb/house/etc."

It now starts from explicit terrain principles:

- `배산/형국`
- `혈 조건`
- `사신사`
- `장풍/감쌈`
- `득수/수계 관계`

Context and profile settings still matter, but they are treated as secondary calibration overlays rather than the first explanation.

### 3. Comparative analysis, not absolute truth claims

- optional site scoring with `fs_score`, `fs_note`, and `fs_reason`
- local calibration with `ROC AUC`, `PR AUC`, `F1`, and threshold diagnostics
- profile/context comparison for exploratory reading

### 4. GIS-native visual interpretation

풍수는 점 몇 개와 얇은 선 몇 개로 끝나지 않습니다.

이 플러그인은 결과를 가능한 한 "몸체감" 있게 보여주도록 바꾸는 중입니다:

- ridges as layered spine/vein ribbons
- hydro as layered flow ribbons
- term points as halo/body/core markers
- structural links as secondary connective anatomy rather than flat wiring

자세한 방향은 [docs/VISUALIZATION.md](docs/VISUALIZATION.md)에 정리했습니다.

---

## Current Real Features

현재 코드 기준으로 실제로 쓸 수 있는 핵심 기능은 다음과 같습니다.

- `DEM + water(optional)` 기반 지형 구조 추출
- supplied water가 없을 때 `auto-hydro` 사용
- `sites` 레이어를 `Point`뿐 아니라 `Polygon`도 입력 가능
- optional Feng Shui term extraction and structural links
- site scoring with principle-first reasoning text
- stable/exploratory preset filtering in the UI
- local calibration reports and threshold inspection fields
- study-case bootstrap tool for repeated experiments:
  `python3 tools/setup_study_case.py ...`

---

## Core Workflow

```text
DEM + Water(optional) + Sites(optional)
        ↓
Terrain extraction
Ridges / Hydro / Terrain metrics
        ↓
Interpretation layers
Terms / Links / Site scoring
        ↓
Comparative reading
Calibration / Compare / Reports / Repeated study cases
```

---

## Quick Start

### 1-minute path

1. Load a DEM in QGIS.
2. Add a water layer if you have one. If not, keep `auto-hydro` enabled.
3. Add a site layer if you want scoring. Point and polygon layers are both accepted.
4. Run terrain extraction first.
5. Turn on term extraction only when you need structure-level reading.
6. Run site analysis after the terrain layers look reasonable.

### Repeated real-data workflow

If you want to test multiple datasets without rebuilding everything every time:

```bash
python3 tools/setup_study_case.py \
  user_cases/gongju_baekje \
  --dem /path/to/666.tif \
  --sites /path/to/tomb_sites.shp \
  --water /path/to/water.shp \
  --title "Gongju Baekje study" \
  --profile tomb
```

This creates a reusable case folder with:

- `case.json`
- `README.md`
- `inputs/`

It also warns when polygon site layers are being reduced to centroid-based interpretation.

---

## Main Outputs

| Layer | Description |
| --- | --- |
| `*_fengshui_ridges` | DEM-derived ridge hierarchy |
| `*_fengshui_hydro` | supplied or DEM-derived hydro network |
| `*_fengshui_terms` | Feng Shui term points |
| `*_fengshui_links` | structural link lines between terms |
| `*_fengshui` | site scoring layer with reasoning fields |

Important site fields:

- `fs_score`
- `fs_note`
- `fs_reason`
- `fs_sashinsa`
- `fs_enclosure`

---

## Trust Model

This plugin is designed for structured interpretation, not final proof.

- `fs_score` is not a probability of site existence.
- context/profile presets are not universal truth.
- calibration is an exploratory signal unless independently validated.
- automated output should be read with field evidence, documentary context, and local expertise.

The most reproducible part of the stack is still:

- DEM handling
- ridge extraction
- hydro extraction
- explicit metric calculation

The least settled part is:

- cultural translation
- profile/context generalization
- strong archaeological claims from score alone

---

## Documentation

### Getting started

- [docs/first_run_guide.md](docs/first_run_guide.md)
- [docs/researcher_quickstart.md](docs/researcher_quickstart.md)

### Interpretation model

- [docs/PRINCIPLES.md](docs/PRINCIPLES.md)
- [docs/VISUALIZATION.md](docs/VISUALIZATION.md)
- [docs/context_profiles.md](docs/context_profiles.md)

### Validation and references

- [docs/validation_protocol.md](docs/validation_protocol.md)
- [docs/research_matrix.md](docs/research_matrix.md)
- [docs/reference_audit.md](docs/reference_audit.md)
- [docs/regional_period_notes.md](docs/regional_period_notes.md)

---

## Requirements

- QGIS `3.28+`
- Python `3.8+`
- projected CRS in meters is strongly recommended
- vector water layer is preferred when interpretation depends heavily on hydro

---

## Repository

- GitHub: [lzpxilfe/Feng-Shui-GIS](https://github.com/lzpxilfe/Feng-Shui-GIS)
