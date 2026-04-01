# 🧭 Feng-Shui GIS

> **Heuristic, terrain-first QGIS plugin for comparative landscape reading inspired by Feng Shui. Not a predictive truth model.**

풍수 해석을 “자동 정답기”가 아니라  
**지형 구조 추출 → 해석 레이어 생성 → 비교/보정 → 재현 가능한 보고**로 이어지는 연구용 GIS 워크플로로 재구성한 QGIS 플러그인입니다.

![QGIS](https://img.shields.io/badge/QGIS-3.28%2B-589632?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat-square)
![Mode](https://img.shields.io/badge/Mode-Quick%20%7C%20Research%20%7C%20Developer-7A5C3E?style=flat-square)
![Output](https://img.shields.io/badge/Outputs-Reports%20%7C%20Manifest%20%7C%20Support%20Bundle-1F6F78?style=flat-square)

---

## 🚪 Start here

| What you need | Where to go |
| --- | --- |
| Safe first run with sample data | 📦 [Sample Project](examples/sample_project/README.md) |
| Fast setup path after install | 🛫 [First Run Guide](docs/first_run_guide.md) |
| Tested baseline and known limits | 🧪 [Tested Versions & Known Limitations](docs/tested_versions.md) |
| When something looks wrong | 🧯 [Troubleshooting](docs/troubleshooting.md) |
| Repro package for maintainers | 🆘 [Support Bundle Guide](docs/support_bundle_guide.md) |
| Issue filing template | 🐞 [Bug Report Template](docs/bug_report_template.md) |

---

## ✨ Why this repository exists

이 저장소의 목표는 단순한 점수 계산기가 아니라,  
풍수적 공간지리 인식을 GIS 위에서 더 **투명하게**, **비교 가능하게**, **재현 가능하게** 읽도록 돕는 것입니다.

우리가 다루는 핵심은 다음 네 가지입니다.

- 🏔️ `DEM` 기반 지형 구조 읽기
- 📍 후보지 점수와 이유 설명
- 🔁 프로파일 비교와 로컬 보정
- 🧾 리포트, manifest, support bundle을 통한 재현성 확보

### 🔎 At a glance

- 입력: `DEM + water(optional) + candidate sites(optional)`
- 핵심 산출물: `ridges`, `hydro`, `site scoring`, `terms`, `links`
- 비교 기능: `profile compare`, `local calibration`
- 운영 산출물: `JSON/Markdown report`, `run manifest`, `benchmark manifest`, `support bundle`

---

## 🎯 Who this is for

### 🔬 Researcher
- 비교 가능한 해석 흐름이 필요한 연구자
- 문화권·시대 맥락을 바꿔가며 결과를 읽고 싶은 사용자
- calibration / compare / evidence trace를 함께 보고 싶은 사용자

### 🎓 Student / Learner
- 풍수 개념을 지형 분석과 연결해 배우고 싶은 사용자
- ridge / hydro / term extraction 중심으로 탐색하고 싶은 사용자

### 🧭 Practitioner
- 최소 입력으로 지형을 빠르게 읽고 싶은 사용자
- 후보지를 비교하고 설명 가능한 결과를 보고 싶은 사용자

---

## 🚀 Quick start

### ⚡ 1-minute start

1. `DEM`을 불러옵니다.
2. 수계 레이어가 있으면 지정하고, 없으면 auto-hydro를 사용합니다.
3. 후보지 포인트가 있으면 지정합니다.
4. 플러그인을 열고 `Quick` 또는 `Research` 흐름으로 진입합니다.
5. `지형 구조 추출` → `입지 분석` 순서로 실행합니다.

### 🔬 5-minute research start

1. 목적 프로파일을 고릅니다. 예: `tomb`, `house`, `settlement`
2. 문화권과 시대를 선택합니다.
3. 필요하면 `용어 추출`을 실행합니다.
4. `캘리브레이션`으로 로컬 튜닝 진단을 확인합니다.
5. `프로파일 비교`로 selected profile 대비 gain/drop을 읽습니다.

## 🗺️ Core workflow

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
Compare / Calibration / Reports / Manifests
```

### 🧩 Working modes

- ⚡ `Quick`
  - 최소 입력
  - 빠른 지형 읽기
  - 연구용 옵션 최소화

- 🔬 `Research`
  - evidence / compare / calibration 중심
  - 문화권·시대 맥락 반영
  - 리포트와 재현성 기록 확인

- 🛠️ `Developer`
  - diagnostics / support bundle / 상태 정보
  - 운영 점검과 공유용 산출물 확인

### 🧭 Representative use cases

- ⚡ `Quick terrain reading`
  - DEM과 water만으로 빠르게 능선/수계/기초 입지 해석층을 확인합니다.

- 🔬 `Research compare / calibration`
  - candidate points와 context를 함께 넣고 compare와 local calibration을 읽습니다.

- 🆘 `Support bundle repro sharing`
  - 이상한 결과가 나오면 bundle을 내보내고 report/manifest와 함께 유지보수 맥락을 공유합니다.

---

## 🌟 Main features

### 🏔️ Terrain extraction
- 능선과 수계를 추출합니다.
- 지형 구조 해석에 필요한 기반 레이어를 생성합니다.
- DEM, 수계, 경사, TPI, convergence 기반 지표를 만듭니다.

### 📘 Term extraction
- 풍수적 구조를 읽기 위한 용어 포인트와 연결선을 생성합니다.
- 혈 후보를 기준으로 구조 용어와 경로 해석층을 시각화합니다.

### 📍 Site analysis
- 후보지에 `fs_score`와 이유 텍스트를 부여합니다.
- 점수만이 아니라 **왜 그렇게 읽혔는지**를 함께 보여줍니다.

### 🔁 Profile compare
- 두 프로파일 사이의 상대 변화량을 비교합니다.
- 결과는 `better/worse` 대신 **selected profile 대비 gain/drop**으로 읽도록 설계되어 있습니다.

### 🧪 Calibration
- 로컬 양성/음성 샘플을 기준으로 튜닝 진단을 수행합니다.
- 학습 / 선택 / 보고 지표를 분리한 payload와 리포트를 제공합니다.

### 🧾 Reporting & reproducibility
- JSON / Markdown report
- run manifest
- benchmark manifest
- calibration / compare audit 정보

### 🆘 Support bundle
- 최신 report / manifest / config / UI snapshot / recent errors를 zip으로 묶습니다.
- 원본 DEM/벡터는 넣지 않고 참조 정보만 보관합니다.

---

## 🔍 Trust model

이 플러그인은 결과를 강하게 단정하지 않도록 설계되어 있습니다.

### 🏷️ Common trust badges

- 🟤 `General Principles`
- 🟠 `Advanced Context`
- 🟡 `Exploratory Context`
- 🟢 `Local Calibration Applied`

### ❗ Read results carefully

- `fs_score`는 **유적 존재 확률**이 아닙니다.
- 이 플러그인은 **heuristic terrain interpretation tool**입니다.
- 이 플러그인은 **predictive truth model이 아닙니다.**
- calibration은 **독립 검증을 대체하지 않습니다.**
- compare는 **선택한 프로파일 대비 상대 변화**입니다.
- 결과는 문헌, 현장 조사, 추가 GIS 해석과 함께 읽어야 합니다.

더 짧은 운영 기준은 [Tested Versions & Known Limitations](docs/tested_versions.md)에서 바로 확인할 수 있습니다.

---

## 📦 Sample project & smoke flows

### 🧪 Sample project

- synthetic DEM / water / sites 제공
- example report payload 포함
- 첫 실행용 기준선 제공

핵심 파일:

- [examples/sample_project/sample_project.qgz](examples/sample_project/sample_project.qgz)
- [examples/sample_project/sample_project.qgs](examples/sample_project/sample_project.qgs)
- [examples/sample_project/README.md](examples/sample_project/README.md)

### ✅ Normal first run should give you

- `fengshui_ridges` or `풍수_산줄기`
- `fengshui_hydro` or `풍수_수계`
- `fengshui` or `풍수_입지평가`
- report example comparison targets from the sample project folder

### 🚦 Smoke & guard scripts

- [tools/run_asset_smoke.py](tools/run_asset_smoke.py)
  - 저장소 자산과 manifest 흐름 점검
- [tools/run_headless_smoke.py](tools/run_headless_smoke.py)
  - QGIS Python 환경에서 analysis / compare / calibration end-to-end smoke
- [tools/release_guard.py](tools/release_guard.py)
  - metadata / README / sample project / fixture / support bundle guard

---

## 📂 Outputs

### 🗺️ QGIS layers

- `풍수_입지평가` / `fengshui`
- `풍수_입지평가_변경지점` / `compare_changes`
- `풍수_산줄기` / `fengshui_ridges`
- `풍수_수계` / `fengshui_hydro`
- `풍수_용어` / `fengshui_terms`
- `풍수_구조연결` / `fengshui_links`
- `풍수_보정` / `calibration`

### 🧾 Reports & operational artifacts

- `reports/feng_shui_run_<service>_<run_id>.json`
- `reports/feng_shui_benchmark_<service>_<run_id>.json`
- `support_bundle_<timestamp>.zip`

---

## 🧠 What this tool is not

- ❌ 자동으로 “좋은 자리”를 확정하는 판정기
- ❌ 역사적 진실을 직접 증명하는 도구
- ❌ 현장 검증 없이 써도 되는 완결형 모델
- ❌ `fs_score`를 확률처럼 읽어도 되는 예측기

이 플러그인의 목표는  
**풍수적 공간지리 인식을 GIS 위에서 더 투명하고, 비교 가능하고, 재현 가능하게 읽도록 돕는 것**입니다.

---

## 🧰 Requirements

- 🧭 QGIS `3.28+`
- 🐍 Python `3.8+`
- 🗺️ 미터 단위 투영좌표계 DEM 권장
- 🌊 선형 water layer가 있으면 더 안정적
- 📍 후보지 포인트 레이어는 선택 입력

### ✅ Recommended setup

- 경위도 CRS보다 projected CRS 사용
- DEM 품질이 낮으면 ridge / hydro / 거리 기반 결과 해석에 주의
- auto-hydro는 보조 수단으로 사용
- 결과는 comparative interpretation frame으로 읽고, predictive result처럼 읽지 않기

---

## 📚 Documentation

### 🛫 Getting started

- [First Run Guide](docs/first_run_guide.md)
- [Researcher Quickstart](docs/researcher_quickstart.md)
- [Tested Versions & Known Limitations](docs/tested_versions.md)
- [Troubleshooting](docs/troubleshooting.md)

### 🔬 Research & validation

- [Validation Protocol](docs/validation_protocol.md)
- [Research Matrix](docs/research_matrix.md)
- [Reference Audit](docs/reference_audit.md)
- [Regional & Period Notes](docs/regional_period_notes.md)
- [Context Profiles](docs/context_profiles.md)

### 🆘 Support & release

- [Support Bundle Guide](docs/support_bundle_guide.md)
- [Bug Report Template](docs/bug_report_template.md)
- [Release Checklist](docs/release_checklist.md)
- [changelog.md](changelog.md)

---

## 🏗️ Repository structure

### Core plugin modules

- `feng_shui_gis/plugin.py`
  - QGIS entrypoint, task wiring, orchestration
- `feng_shui_gis/dock_widget.py`
  - workflow UI, state application, trust/status surface
- `feng_shui_gis/analysis.py`
  - terrain analysis orchestration engine

### Service / reporting / support

- `feng_shui_gis/services/analysis_service.py`
  - analysis / compare / calibration service boundary
- `feng_shui_gis/reporting/`
  - compare / calibration / support bundle writers
- `feng_shui_gis/trust_metadata.py`
  - trust badges and shared interpretation metadata

### Tests / fixtures / tools

- `tests/`
  - contract tests, fixture contracts, productization regression skeleton
- `examples/sample_project/`
  - synthetic baseline project
- `tools/`
  - smoke, benchmark, release guard helpers

---

## 🤝 Contributing / reporting

문제 제보나 재현 공유가 필요할 때는 아래 순서를 권장합니다.

1. `Support Bundle`을 생성합니다.
2. [Bug Report Template](docs/bug_report_template.md)에 맞춰 상황을 정리합니다.
3. 가능하면 사용한 DEM / water / site 레이어의 CRS와 해상도를 함께 적어 주세요.

---

## 🔗 Repository

- GitHub: [lzpxilfe/Feng-Shui-GIS](https://github.com/lzpxilfe/Feng-Shui-GIS)
