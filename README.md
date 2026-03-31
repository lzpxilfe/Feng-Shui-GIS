# Asian Landscape Reader (Feng Shui GIS)

QGIS plugin for terrain-first, evidence-aware landscape interpretation in historical and archaeological contexts.

## 핵심 목표 / What this plugin is for

- **입지 분석의 3단계 파이프라인**을 UI에서 강제로 안내:
  1) 데이터 준비, 2) 지형 추출, 3) 후보지 점수/보정
- 지역·시대·반구 가정은 **설정 가능한 컨텍스트**로 분리하고, 결과에 영향이 남도록 명시
- 고급 실험 설정은 노출은 낮추고, 필요 시 **전문 모드(Expert)** 로 전환
- 실행 기록(리포트, 히스토리, 설정)을 남겨 재현성과 검증성을 높임

## 현재 구조

- `feng_shui_gis/dock_widget.py`
  - 작업 인터페이스와 실행 흐름 가이드, 컨텍스트 패널
- `feng_shui_gis/plugin.py`
  - 각 탭 액션(지형 추출/용어 추출/점수 분석/보정) 실행 진입점
- `feng_shui_gis/analysis.py`
  - 점수 계산, 보정, 출력 레이어 생성, 리포트 작성
- `feng_shui_gis/cultural_context.py`, `references.json`, `contexts.json`, `profiles.json`
  - 문화권·시대·근거 프리셋/출처 데이터 계층

## 주요 기능

### 1) 기본 모드 (Basic)

- 목표(무덤/주거/정착지/일반)와 레이어 지정
- 산줄기/수계 흐름 위주의 분석을 기본 모드에서 먼저 실행
- 지역/시대 고급 옵션은 기본적으로 축소/자동 비활성화

### 2) 용어·구조 추출 (Landscape / Terms)

- 반구/DEM/수계(또는 자동 수계)를 기반으로 지형 구조 추출
- 필요 시 용어 점 및 연결선 생성

### 3) 분석 & 점수 계산 (Analysis)

- 후보지(포인트) 기반 점수 계산
- 점수 근거(reason) 레이어 필드 노출
- 시각화/요약 뷰에서 진행률과 다음 동작 안내

### 4) 로컬 보정 (Calibration)

- 후보지 점수 데이터셋 기준으로 지역/시대 맥락 기반 보정 시도
- ROC/PR 지표, 적용 전후 비교, 변경 내역을 리포트(JSON+Markdown)로 기록
- 보정된 프로파일은 로컬 저장소에 버전성 있게 저장 가능

## UI 가이드: workflow mode

- **Basic (기본)**: 초보자/빠른 실행에 맞춘 최소 화면.
- **Expert (전문)**: 프리셋, 문화권, 시대, 컨텍스트 근거 패널을 수동으로 조절.

> Advanced Context 버튼은 기존과 동일하게 유지되지만, 기본 모드에서는 자동으로 숨김 상태가 기본입니다.

## 설치 / 실행

1. QGIS의 Python Plugin 경로에 플러그인 폴더 추가
2. 플러그인 활성화
3. 패널에서 DEM 선택
4. 수계 레이어를 넣거나 DEM 자동 수계 사용
5. 후보지 포인트 지정(선택)
6. `지형 구조 추출` 실행
7. 필요 시 용어 추출 또는 분석 탭으로 이동

## 사용자 언어

- UI 라벨: **한국어 / English** 토글
- 용어 라벨 언어(결과 텍스트)도 별도 토글

## 문서

- [docs/context_profiles.md](docs/context_profiles.md)
- [docs/reference_audit.md](docs/reference_audit.md)
- [docs/research_matrix.md](docs/research_matrix.md)
- [docs/regional_period_notes.md](docs/regional_period_notes.md)
- [docs/researcher_quickstart.md](docs/researcher_quickstart.md)
- [docs/validation_protocol.md](docs/validation_protocol.md)

## 제한/전제 (Honest notes)

- 자동 추출은 DEM 품질에 크게 영향을 받습니다.
- 지역/시대 프리셋은 `연구 가설`을 검증하는 도구이지 현장 진단을 대체하지 않습니다.
- 실험적 프로파일은 탐색용이며, 최종 결론은 추가 검증이 필요합니다.
