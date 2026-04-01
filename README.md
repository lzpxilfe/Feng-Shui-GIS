# 🧭 Feng-Shui GIS

> **Terrain-first, evidence-aware QGIS plugin for reading historical landscapes through geomorphology, context, and comparative interpretation.**

풍수 해석을 “자동 정답기”가 아니라,  
**지형 구조 → 해석 레이어 → 비교/보정 → 재현 가능한 리포트**로 이어지는 연구 도구로 재구성한 QGIS 플러그인입니다.

---

## ✨ What this plugin does

- 🏔️ `DEM` 기반으로 능선, 수계, 지형 지표를 추출합니다.
- 📍 후보지 레이어에 대해 `fs_score`와 `reason`을 함께 생성합니다.
- 🧪 프로파일 비교와 로컬 캘리브레이션으로 해석 차이를 점검합니다.
- 🧾 보고서, run manifest, benchmark manifest를 남겨 재현성을 확보합니다.
- 🧰 `Support Bundle`로 현재 상태를 묶어 공유할 수 있습니다.

---

## 🎯 Who this is for

### 🔬 Researcher
- 재현 가능한 분석 흐름이 필요한 연구자
- 문화권/시대 맥락을 바꿔 비교 실험을 하고 싶은 사용자
- calibration / compare / evidence trace를 함께 보고 싶은 사용자

### 🎓 Student / Learner
- 풍수 개념을 GIS 지형 분석과 연결해서 배우고 싶은 사용자
- terrain, ridge, hydro, term extraction 중심으로 탐색하고 싶은 사용자

### 🧭 Practitioner
- 빠르게 지형을 읽고 후보지를 비교해 보고 싶은 사용자
- Quick 모드에서 최소 입력으로 결과를 보고 싶은 사용자

---

## 🚀 Quick start

### 1분 시작

1. `DEM`을 불러옵니다.
2. 수계 레이어가 있으면 지정하고, 없으면 자동 수계를 사용합니다.
3. 후보지 포인트가 있으면 지정합니다.
4. 플러그인을 열고 `Quick` 또는 `Research` 모드를 선택합니다.
5. `지형 구조 추출` → `입지 분석` 순서로 실행합니다.

### 5분 시작

1. 목표 프로파일을 선택합니다. 예: `tomb`, `house`, `village`
2. 문화권과 시대를 고릅니다.
3. 필요하면 `용어 추출`을 실행합니다.
4. `캘리브레이션`으로 로컬 튜닝 진단을 확인합니다.
5. `프로파일 비교`로 gain/drop relative to selected profile을 읽습니다.

### 바로 들어가기

- 📦 [Sample Project](examples/sample_project/README.md)
- 🛫 [First Run Guide](docs/first_run_guide.md)
- 🧯 [Troubleshooting](docs/troubleshooting.md)
- 🆘 [Support Bundle Guide](docs/support_bundle_guide.md)
- 🐞 [Bug Report Template](docs/bug_report_template.md)

---

## 🗺️ Core workflow

```text
[Input]
DEM + Water(optional) + Sites(optional)
   ↓
[Step 1] Terrain extraction
Ridges / Hydro / Terrain metrics
   ↓
[Step 2] Interpretation layers
Terms / Links / Site scoring
   ↓
[Step 3] Comparative reading
Compare / Calibration / Reports / Manifests
```

### 실제 작업 모드

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

---

## 🧩 Main features

### 🏔️ Terrain extraction
- 능선과 수계를 추출합니다.
- 지형 구조 해석에 필요한 기반 레이어를 생성합니다.

### 📘 Term extraction
- 풍수적 구조를 읽기 위한 용어 포인트와 연결선을 만듭니다.
- 지형 해석층을 시각적으로 확인할 수 있습니다.

### 📍 Site analysis
- 후보지에 `fs_score`와 이유 텍스트를 부여합니다.
- 점수만이 아니라 **왜 그렇게 읽혔는지**를 함께 봅니다.

### 🔁 Profile compare
- 두 프로파일 사이의 상대 변화량을 비교합니다.
- 결과는 `better/worse`가 아니라 **selected profile 대비 gain/drop**으로 읽도록 설계되어 있습니다.

### 🧪 Calibration
- 로컬 양성/음성 샘플을 기준으로 튜닝 진단을 수행합니다.
- 학습/선택/보고 분리를 유지한 payload와 리포트를 제공합니다.

### 🧾 Reporting & reproducibility
- JSON / Markdown report
- run manifest
- benchmark manifest
- calibration / compare audit 정보

### 🆘 Support bundle
- 최신 report / manifest / config / UI snapshot / recent errors를 zip으로 묶습니다.
- 원본 DEM/벡터는 포함하지 않고 참조 정보만 보관합니다.

---

## 🔍 Trust model

이 플러그인은 결과를 강하게 단정하지 않도록 설계되어 있습니다.

### 공통 trust badge

- 🟤 `General Principles`
- 🟠 `Advanced Context`
- 🟡 `Exploratory Context`
- 🟢 `Local Calibration Applied`

### 반드시 기억할 점

- `fs_score`는 **유적 존재 확률**이 아닙니다.
- calibration은 **독립 검증을 대체하지 않습니다.**
- compare는 **선택한 프로파일 대비 상대 변화**입니다.
- 결과는 문헌, 현장 조사, 추가 GIS 해석과 함께 읽어야 합니다.

---

## 🧪 Sample project & smoke flows

### Sample project

- synthetic DEM / water / sites 제공
- expected report 예시 포함
- 실제 첫 실행용 기준선 제공

파일:
- [examples/sample_project/sample_project.qgz](examples/sample_project/sample_project.qgz)
- [examples/sample_project/README.md](examples/sample_project/README.md)

### Smoke & guard scripts

- [tools/run_asset_smoke.py](tools/run_asset_smoke.py)
  - 저장소 자산과 manifest 흐름 점검
- [tools/run_headless_smoke.py](tools/run_headless_smoke.py)
  - QGIS Python 환경에서 analysis / compare / calibration end-to-end smoke
- [tools/release_guard.py](tools/release_guard.py)
  - metadata / README / sample project / fixture / support bundle guard

---

## 📂 Outputs

대표 산출물:

- `풍수_입지평가` / `fengshui`
- `풍수_입지평가_변경지점` / `compare_changes`
- `풍수_산줄기` / `fengshui_ridges`
- `풍수_수계` / `fengshui_hydro`
- `풍수_용어` / `fengshui_terms`
- `풍수_구조연결` / `fengshui_links`
- `풍수_보정` / `calibration`

보고서/운영 기록:

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

권장 사항:

- 경위도 CRS보다 projected CRS 사용
- DEM 품질이 낮으면 ridge/hydro/거리 기반 결과 해석에 주의
- auto-hydro는 보조 수단으로 사용

---

## 📚 Documentation

### Getting started

- [First Run Guide](docs/first_run_guide.md)
- [Researcher Quickstart](docs/researcher_quickstart.md)
- [Troubleshooting](docs/troubleshooting.md)

### Research & validation

- [Validation Protocol](docs/validation_protocol.md)
- [Research Matrix](docs/research_matrix.md)
- [Reference Audit](docs/reference_audit.md)
- [Regional & Period Notes](docs/regional_period_notes.md)
- [Context Profiles](docs/context_profiles.md)

### Support & release

- [Support Bundle Guide](docs/support_bundle_guide.md)
- [Bug Report Template](docs/bug_report_template.md)
- [Release Checklist](docs/release_checklist.md)
- [changelog.md](changelog.md)

---

## 🏗️ Repository highlights

- `feng_shui_gis/plugin.py`
  - QGIS entrypoint, task wiring, orchestration
- `feng_shui_gis/dock_widget.py`
  - workflow UI, mode switching, trust/status surface
- `feng_shui_gis/analysis.py`
  - terrain analysis and scoring engine
- `feng_shui_gis/reporting/`
  - compare / calibration / support bundle writers
- `feng_shui_gis/services/analysis_service.py`
  - service boundary for analysis, compare, calibration

---

## 🌏 Why this project matters

이 프로젝트는 풍수를 “신비화”하지 않고,  
반대로 너무 단순한 점수 모델로 축소하지도 않으려 합니다.

우리가 만들고 있는 것은:

- 지형을 먼저 읽고
- 해석의 근거를 남기고
- 문화권/시대 차이를 비교하고
- 결과를 재현 가능하게 공유하는

**아시아 역사 공간지리를 읽기 위한 GIS 플러그인**입니다.
