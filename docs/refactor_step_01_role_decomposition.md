# 1단계: `plugin.py` / `dock_widget.py` / `analysis.py` 역할 분해 문서

작성일: 2026-03-31  
범위: Feng-Shui GIS 리팩토링 v1 (검증·설명가능성·운영성 강화)

## 1) 목표

이 단계의 목적은 코드 동작 변경이 아니라 **현 상태를 기준으로 역할 경계를 명확히 고정**하는 것입니다.  
다음 단계(P0~P2)에서 리팩토링 범위를 추적 가능하게 만들기 위해 다음을 문서화합니다.

- 현재 책임 주체(Owner) 정의
- 파일 간 호출 관계(현재 호출 그래프) 기록
- 타겟 아키텍처(서비스/어댑터/도메인/보고 계층)에 매핑할 기준

## 2) 현재 책임 분해(현실 기반)

### 2.1 `feng_shui_gis/plugin.py` (현재 책임 과다)

`FengShuiGisPlugin`가 실질적으로 담당하는 영역:

- 진입/바인딩:
  - `__init__`, `initGui`, `unload`, `toggle_panel`, `run*` 슬롯 연결
- 분석 오케스트레이션:
  - `run_analysis`, `run_term_extraction`, `run_profile_compare`, `run_calibration`
- 입력 검증 + 지도 계측 검증:
  - 레이어 체크, CRS 일치성/지리좌표 경고, 자동 수계 생성
- 분석 엔진 호출 및 실행 결과 보정:
  - `FengShuiAnalyzer` 생성/호출
  - 산명 조회, 출력 레이어 명 생성/이름 정책
- 출력 조립:
  - 레이어 삽입(`_insert_output_layers`) 및 필드 alias/표시
- 비교/증명 로직:
  - `_pairwise_score_delta`, `_top_score_changes`, 선택·줌·레이어 우선순위
- 렌더링/팝업/리포트 생성:
  - 마크다운/HTML 테이블 포맷, 비교/캘리브레이션 리포트 문자열 생성
- 로그/메시지:
  - 메시지바/사용자 경고 + 디버그 로그

**문제:** 분석 엔진(도메인), I/O(레이어 조작), 렌더링/리포트, UI 이벤트 처리가 `plugin.py` 안에 섞임.

### 2.2 `feng_shui_gis/dock_widget.py` (현재 책임 과다)

`FengShuiDockWidget`가 담당하는 영역:

- UI 렌더링:
  - 다이얼로그/패널/탭/헬프/툴팁/스타일시트 구성
- 상태 관리:
  - UI 상태 스냅샷/복원 (`_snapshot_ui_state`, `_restore_ui_state`)
- 입력 조합:
  - 지역/시대/프로파일/모드/실행옵션 처리
- 상태 기반 제어:
  - 고급 옵션 토글, 추천 프로파일 적용, 목표 기반 가이드 UI 갱신
- 이벤트 발행:
  - `run_requested`, `compare_requested`, `terms_requested`, `calibration_requested` 시그널
- 사용자 피드백:
  - 상태 텍스트, 프리뷰 힌트, 데모/증거 요약/DEM 진단 UI 갱신

**문제:** UI 빌더, 워크플로우 상태머신, 도메인 힌트 계산(간단한 추천 로직)까지 공존.

### 2.3 `feng_shui_gis/analysis.py` (현재 책임 과다)

`FengShuiAnalyzer`가 담당하는 영역:

- 분석 도메인:
  - 점수 계산/규칙 조회 (`_score_*`), 보정/평가 지표
- 피처 처리:
  - 샘플링, 네거티브 포인트 생성, DEM 샘플링
- 용어/지형 추출 파이프라인:
  - `extract_terms`, `build_term_links`, `build_hydro_network`, `build_ridge_network`
- 스타일/레이어 구성:
  - `style_term_points`, `style_term_links`, `style_hydro_network`, `style_ridge_network`,
    `_as_vector_layer`, `_as_raster_layer`
- 출력/메타:
- 보고 성격의 문서 구성 일부 (`_metadata_*`, 근거 문자열 생성 함수)

**문제:** 순수 계산 도메인과 QGIS 레이어 조작, 렌더링, 산학적 메타 라벨링이 뒤섞임.

## 3) 현재 호출 그래프(1차 추출)

```mermaid
flowchart TD
  U[UI Layer]
  U -->|run request signals| DW[FengShuiDockWidget]
  DW -->|run_requested| PL[FengShuiGisPlugin.run_analysis]
  DW -->|compare_requested| PL2[FengShuiGisPlugin.run_profile_compare]
  DW -->|terms_requested| PL3[FengShuiGisPlugin.run_term_extraction]
  DW -->|calibration_requested| PL4[FengShuiGisPlugin.run_calibration]

  PL -->|constructs context & call| AN[FengShuiAnalyzer]
  PL2 -->|constructs context & call| AN2[FengShuiAnalyzer]
  PL3 -->|constructs context & call| AN3[FengShuiAnalyzer]
  PL4 -->|constructs context & call| AN4[FengShuiAnalyzer]

  AN -->|_collect_points,_sample_negative_points,etc| PR[Processing (qgis.processing)]
  AN -->|build_* network| R2[Terrain Extraction]
  AN -->|_score_*/_compose_*| SR[Scoring Rules]
  AN -->|style_* | ST[Layer Styling]
  AN -->|_as_vector_layer| LO[Layer Output]

  PL -->|_style/_reason/_report helpers| UIO[Layer styling + popups + report rendering]
  PL -->|_warn/_select/_zoom| UIB[QGIS UI feedback]
  PL -->|_insert_output_layers| QGISL[Project Layer Registry]
```

## 4) 분해 대상 매핑(이번 단계 산출물)

다음 단계에서 사용 가능한 1차 매핑 기준:

### `plugin.py`

- 진입점 + 시그널/슬롯 유지
- `FengShuiGisPlugin`의 역할은 **adapter layer**
- 남길 것: `__init__`, `initGui`, `unload`, `toggle_panel`, 요청 수신 및 서비스 호출 라우팅
- 대상에서 분리할 것:
  - 출력 레이어 조립/리포트 문자열/비교 정책/렌더링 유틸의 대부분

### `dock_widget.py`

- UI 위주로 축소
- 남길 것: 상태 표현, 입력 폼, 다이얼로그, 시그널 발행
- 대상에서 분리할 것:
  - 목표/추천/증거/가이드 계산의 도메인적 결정을 ViewModel/상태서비스로 이동

### `analysis.py`

- `FengShuiAnalyzer`를 계산 중심으로 정리
- 남길 것: 순수 점수/보정/샘플링 핵심 규칙 + 결과 DTO 생성
- 대상에서 분리할 것:
  - 레이어 스타일링, 레이어 입출력 포맷/HTML/Markdown 문자열 조립, UI 친화적 문구 조립

## 5) 이번 단계 완료 기준 (Definition of Done)

- 위 문서(`docs/refactor_step_01_role_decomposition.md`)가 최신 소유 책임을 반영함.
- 단계 1에서 분해할 책임 목록이 모두 명시됨.
- 다음 단계의 설계 산출물(`Step 2`)에서 바로 참조 가능한 호출 경계/책임 표가 존재함.
- 현재 코드 동작은 이 단계에서 변경하지 않음(분해 문서화만 수행).

### 1.1 보완: 최신 단계 문서

- Step 2~3 호출 그래프 + 서비스 설계안은 다음 문서에 정리됨:
  - [docs/refactor_step_02_call_graph_and_services.md](docs/refactor_step_02_call_graph_and_services.md)

## 6) 다음 단계

- 2단계: 재현성 계약 정비 (`tests/test_reproducibility_contract.py` 중심)  
- 3단계: feature 매칭/비교 정합성 기준(`feature_id`→`uid`) 정립
- 4단계: calibration vs validation 분리 강제 + seed/seedless 분기
