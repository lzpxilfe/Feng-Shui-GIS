# 리팩토링 단계 1: 호출 경로/역할 분해 문서

작성일: 2026-04-01  
목표: 기능 추가가 아닌 **안정성·설명가능성·운영성 강화**를 위한 리팩토링을 실행하기 전에, 현재 상태를 명시적으로 분해한다.

## 1) 현재 엔트리 포인트와 호출 그래프

### 1.1 사용자 트리거 → Dock → Plugin

- `FengShuiDockWidget`에서 시그널 방출
  - `run_requested(site_layer, dem_layer, water_layer, hemisphere, profile_key, culture_key, period_key, auto_hydro)`
  - `run_profile_compare(...)`
  - `run_calibration(...)`
  - `run_term_extraction(...)`
  - `cancel_requested()`
- `FengShuiGisPlugin.toggle_panel()`에서 시그널-핸들러 연결
- 각 시그널은 `plugin.py`의 대응 메서드(`run_analysis`, `run_profile_compare`, `run_calibration`, `run_term_extraction`)로 진입

### 1.2 Plugin → Service → Analysis Engine

#### 분석 (`run_analysis`)
1. UI 입력 가드 (`sites`, `dem`, CRS 경고/유효성)
2. `AnalysisRequest` 생성
3. `_run_background_task(...)`로 작업을 비동기 처리
4. 백그라운드에서 `self._analysis_service.run_analysis(request)` 호출
5. 완료 시 결과 레이어 정리/표시:
   - 산줄기명 조회
   - 클릭 정보 연결
   - 결과 메시지/상태 갱신

#### 비교 (`run_profile_compare`)
1. UI 입력 가드 + context/cors 처리
2. `CompareRequest` 생성
3. `_run_background_task(...)`로 비동기 실행
4. 백그라운드에서 `run_profile_compare`(service)
5. UI thread에서 결과 정합성 검증:
   - `_validate_compare_feature_contract`
   - `_top_score_changes`
   - `_validate_compare_top_change_contract`
6. 비교 레이어/상태 레이어 생성 및 export/report 표시

#### 캘리브레이션 (`run_calibration`)
1. UI 입력 가드 + context 정규화 (`_resolved_calibration_context`)
2. `CalibrationRequest` 생성
3. `_run_background_task(...)`로 비동기 실행
4. 백그라운드에서 `run_calibration`(service)
5. UI thread에서 결과 검증:
   - `_validate_calibration_feature_contract`
   - calibration report 작성 및 profile export

#### 용어 추출 (`run_term_extraction`)
1. DEM + 옵션 입력 검증
2. `TermExtractionRequest` 생성
3. `_run_background_task` 수행
4. 결과 레이어(산줄기/수계/용어점/용어연결선) 정렬 표시

## 2) 책임 분해(현재 구현 기준)

### 2.1 `plugin.py` (현재 “진입 어댑터 + 오케스트레이터 + I/O glue”)
- 담당
  - UI 시그널 연결/취소/상태표시
  - 백그라운드 태스크 런처와 공통 예외 처리
  - 레이어 결과의 이름 지정, 스타일 지정, 레이어 등록
  - compare/calibration 결과 검증 + 레포트/내보내기 I/O
  - 산줄기 조회/선택/줌핑/팝업 호출
- 경계 밖으로 밀어낼 후보
  - 결과 정렬/계산 로직(현재 거의 없음)
  - 성능/검증 정책(부분적으로 뷰모델에 분리)

### 2.2 `analysis.py` (도메인 계산기)
- 담당
  - DEM 처리, 샘플링, 스코어 계산
  - 캘리브레이션 적합/분할/지표 계산
  - 산줄기/수계/용어 추출 등 GIS 산출
- 주의
  - 현재 `_fit_local_calibration_weights`에 split/evaluation 경로가 반영되어 있음
  - 보고 메트릭/레포트 데이터는 서비스-플러그인 경계에서 소비

### 2.3 `dock_widget.py` (UI + ViewModel 연동)
- 담당
  - 입력 폼 구성/상태 갱신/버튼 가용/워크플로우 가이드 갱신
  - 분석/비교/캘리브레이션/취소 시그널 emit
  - 상태표시(progress/guide)
- 현재 분해 포인트
  - 추천/워크플로우 정책의 상당 부분이 `dock_widget_viewmodel.py`로 이동됨
  - 남은 UI 결정성 텍스트/표시 로직은 `widget`에서 운영 중

### 2.4 `dock_widget_viewmodel.py` (표시용 상태/정책 뷰모델)
- 담당
  - 추천 프로필 제안/비교 가능성 판단
  - 워크플로우 체크스트립트 계산
  - 라벨 텍스트 키/기본값 조합 및 표시 텍스트 생성

## 3) 현재 단계 판정

- 단계 1(역할분해 문서화)은 `docs/refactor_step1_architecture_boundaries.md`로 완료.
- 다음 단계 제안(2): `analysis.py`/`plugin.py`의 검증 계약과 예외 경로를 테스트 계약으로 정식 고정
  - seed 고정 재현성
  - 캘리브레이션 분할/평가 분리 불변성
  - 비교/캘리브레이션에서 UID 정합성 fail-closed

## 4) 현재 단계에서의 다음 액션 권고

1. `service_contracts`/리포트 스키마 기반으로 `calibration_split`/`compare_contract`를 테스트 가능한 계약으로 노출
2. `run_profile_compare`에서 `top_change` 행의 UID 누락·누락셋에 대한 fail-closed 예외를 단위 테스트로 고정
3. `run_calibration`의 후보 탐색/최종 지표를 “훈련-선정-평가” 분리 구조로 문서화된 주석/계약과 함께 검증
