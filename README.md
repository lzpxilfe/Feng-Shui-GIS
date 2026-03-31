# 🧭 Asian Landscape Reader (Feng Shui GIS)

**QGIS plugin for terrain-first, evidence-aware landscape interpretation in historical and archaeological contexts.**

---

## ✨ 한 줄 설명

고전 풍수(풍수) 관점의 공간 읽기를 GIS로 재구성한 플러그인으로,  
`DEM`에서 지형 구조를 먼저 추출한 뒤 후보지의 형국 적합도를 점수화하고,  
지역/시대 문맥을 반영한 보정까지 가능한 **3단계 분석 워크플로**를 제공합니다.

---

## 🎯 왜 이 플러그인을 쓰나요?

- ✅ 지형 기반 분석을 우선해 과도한 추론을 줄이고, 산수(地形) 근거를 먼저 확보할 수 있습니다.
- ✅ 후보지 점수와 함께 근거(reason)를 함께 확인해 해석 투명성을 높입니다.
- ✅ 동일 데이터에서 지역·시대 설정을 바꿔 **비교 실험**을 쉽게 수행합니다.
- ✅ 작업 이력(리포트/히스토리)을 남겨 재현 가능한 분석 체계를 만듭니다.

---

## 🧩 핵심 구조

[feng_shui_gis/dock_widget.py](feng_shui_gis/dock_widget.py): UI, 입력 검사, 모드 전환, 진행 안내
[feng_shui_gis/plugin.py](feng_shui_gis/plugin.py): 액션 진입점, 레이어 생성/삽입, 리포트 연동
[feng_shui_gis/analysis.py](feng_shui_gis/analysis.py): 지형 연산, 점수 계산, 비교, 보정, 레이어 생성
[feng_shui_gis/cultural_context.py](feng_shui_gis/cultural_context.py): 지역·시대 컨텍스트 규칙
[feng_shui_gis/reference_catalog.py](feng_shui_gis/reference_catalog.py): 근거 텍스트 매핑 및 표기
[docs/research_matrix.md](docs/research_matrix.md): 참고 근거/근거 수준 정리

---

## ⚙️ 주요 기능

### 🗺️ 1) 기본 분석 워크플로

1. **Terrain Extraction (지형 추출)**
   - 능선(라인), 수계(라인), 토지형 연산에 필요한 산학(地形) 기초 지표 산출
2. **Landscape / Term Extraction (용어·구조 추출)**
   - 해석 단위를 표현하는 용어 포인트, 구조 연결선 생성
3. **Site Analysis (입지 분석)**
   - 후보지 점수(`fs_score`), 지표별 적합도, 근거(reason) 저장
4. **Calibration (보정)**
   - 로컬 양성/음성 샘플 기반으로 지역/시대별 가중치 및 임계치 재조정
5. **Profile Compare (프로파일 비교)**
   - 보정 전후 또는 서로 다른 프로파일의 변화량을 비교 레이어로 확인

### 🧪 2) 실험 모드 설계

- `기본 모드`는 초보자용 최소 화면으로 핵심 분석을 빠르게 수행합니다.
- `전문 모드`는 프로파일, 문화권, 시대, 컨텍스트 패널을 수동 조절합니다.
- `Advanced Context`는 필요 시만 노출되어 복잡도를 줄여줍니다.

### 🌐 3) 이중 언어 UX

- UI 언어: **한국어 / English**
- 라벨 언어: 결과 필드명/툴팁/맵팁을 별도 조정 가능
- 레이어 생성 시 언어별 접미사 자동 적용

### 📈 4) 산출물 가시성

- 클릭 툴팁(`MapTip`)과 필드 별칭(alias)이 분석 유형별로 다국어로 정리
- 후보지/레포트에서 근거 텍스트를 함께 노출
- 보정 지표(ROC AUC, PR AUC, F1, Youden J) 비교표를 텍스트/HTML 두 형태로 제공

---

## 📥 설치 및 실행

1. QGIS에서 플러그인 경로에 코드를 배치합니다.
2. 플러그인을 활성화하고 패널을 엽니다.
3. DEM 레이어를 지정합니다.
4. 수계 레이어가 있으면 지정하고, 없으면 자동 수계(옵션)를 사용합니다.
5. 후보지 포인트 레이어를 지정합니다(선택).
6. `지형 구조 추출` → `용어 추출(필요 시)` → `분석` 순서로 진행합니다.
7. 필요 시 `보정`을 실행하고 비교 리포트를 확인합니다.

### 권장 입력 조건

- EPSG 단위가 미터인 투영좌표계 DEM을 권장합니다.
- 수위 거리/반경 기반 지표는 CRS 유닛 해상도와 DEM 품질에 민감합니다.

---

## 🧬 분석 레이어와 출력

- `풍수_입지평가` / `fengshui` : 후보지 점수 및 근거 레이어
- `풍수_입지평가_변경지점` / `compare_changes` : 비교(변화) 레이어
- `풍수_산줄기` / `fengshui_ridges` : 산줄기(능선) 벡터
- `풍수_수계` / `fengshui_hydro` : 수계 벡터
- `풍수_용어` / `fengshui_terms` : 용어 포인트
- `풍수_구조연결` / `fengshui_links` : 용어 연결선
- `풍수_보정` / `calibration` : 보정 결과 레이어

> 위 명칭은 UI 언어 설정(ko/en)에 따라 표시됩니다.

---

## 🧠 근거와 한계

- 이 도구의 목적은 점수를 “절대 진리”로 제시하는 것이 아니라,  
  **근거 기반의 비교 가능한 해석 프레임**을 제공하는 것입니다.
- 지역/시대 프리셋은 가설 기반 보정 계층으로, 실측/현장 검증이 필요합니다.
- 수계·능선 자동 추출은 DEM 품질의 영향을 크게 받습니다.

---

## 📚 문서

- [docs/context_profiles.md](docs/context_profiles.md)
- [docs/reference_audit.md](docs/reference_audit.md)
- [docs/research_matrix.md](docs/research_matrix.md)
- [docs/regional_period_notes.md](docs/regional_period_notes.md)
- [docs/researcher_quickstart.md](docs/researcher_quickstart.md)
- [docs/validation_protocol.md](docs/validation_protocol.md)

---

## 🛠️ 추가 팁

- 실행 전 [projection]이 degree(경위도)면 거리 기반 계산에서 정확도 저하가 발생할 수 있어,
  미터 기반 CRS로 재투영 후 사용하는 것을 권장합니다.
- 산출 레이어에서 `reason`/`fs_reason`을 확인하면 각 점수의 설명성을 빠르게 점검할 수 있습니다.
- 보정 리포트는 실험 이력으로 누적되어, 추후 비교 분석(시대/국가별 분리)에 유리합니다.

---

## ⚖️ 사용 제한

- 자동 추출/보정은 보조 판단 도구이며, 최종 의사결정은 현장 조사와 추가 검증을 함께 사용하세요.
- 실험용 프로파일은 탐색적 성격이 강합니다.
