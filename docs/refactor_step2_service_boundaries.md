# 리팩토링 단계 2: 호출 그래프 + 서비스 경계 설계안 (실행 준비본)

작성일: 2026-04-01  
목표: 현재 모놀리식 동작을 단계적으로 `adapter / service / domain / reporting`으로 분리하기 위한 실행 가능한 경계안 제시.

## A. 현재 실제 호출 그래프 (요약)

### A.1 분석 실행

- `FengShuiGisPlugin.run_analysis`
  - `run_analysis_service` via `FengShuiAnalysisService.run_analysis`
    - `FengShuiAnalyzer.run`
      - `build_hydro_network` (옵션)
      - `run` (DEM raster sampling, score calc, field 보정, 스타일링)
  - `_run_background_task` 완료 시 plugin에서:
    - 산명 조회, 레이어 등록, 스타일링, 상태 메시지

### A.2 비교 실행

- `FengShuiGisPlugin.run_profile_compare`
  - `FengShuiAnalysisService.run_profile_compare`
    - `FengShuiAnalyzer.run(base profile)`
    - `FengShuiAnalyzer.run(compare profile)`
  - plugin에서 비교 후 처리:
    - ` _validate_compare_feature_contract`
    - `_top_score_changes` / `_validate_compare_top_change_contract`
    - selection + zoom + change-layer export + 보고서 저장

### A.3 캘리브레이션 실행

- `FengShuiGisPlugin.run_calibration`
  - `FengShuiAnalysisService.run_calibration`
    - `FengShuiAnalyzer.calibrate`
      - `_build_calibration_input_layer`
      - `_fit_local_calibration_weights`
      - `_annotate_calibration_layer`
  - plugin에서 결과 계약 검증:
    - `_validate_calibration_feature_contract`
    - calibration report/export

### A.4 용어 추출

- `FengShuiGisPlugin.run_term_extraction`
  - `FengShuiAnalysisService.run_term_extraction`
    - `build_ridge_network`
    - `extract_terms`
    - `build_term_links`
  - plugin에서 결과 레이어 등록/표시

## B. 제안 서비스 경계 (요청된 architecture 항목별)

- `qgis_io` adapter
  - 레이어 write/read, materialize, selection/zoom, 프로젝트 레이어 등록
- `qgis_rendering` adapter
  - symbology, label/text style, 색상/범례 설정
- `application services`
  - `run_analysis_service` : 요청 유효성/엔진 실행/결과 출력 보증
  - `compare_service` : base/compare 실행 + top-change 계산 + 정합성 계약
  - `calibration_service` : 분할/튜닝/지표 평가/캘리브레이션 결과 계약
  - `term_extraction_service` : 산줄기/용어 추출/용어 연결선
- `domain`
  - `scoring` : 점수 계산 규칙(향후 metric naming 정형화)
  - `calibration` : split/evaluation/fallback 판정 규칙
  - `context_model` : 문화권/시대/정상/실험 레벨 병합
  - `mountain_matching` : 산명 서비스 연동/캐싱/오류 구간 처리
- `reporting`
  - `calibration_report_writer`
  - `compare_report_writer`

## C. 현재 경계 누수 포인트 (우선 보완 대상)

1. `plugin.py`에 UI/결과 가공의 일부가 남아 있음
   - top-change 테이블 구성, 레이어 결과 유효성 검사, 보고서 텍스트 포맷
2. `dock_widget.py`가 일부 정책성 판단을 아직 유지
   - 예: 단계 가이드 문구/권장 액션 구성(현재는 viewmodel 기반 계산이 일부 존재)
3. `analysis.py`는 계산 도메인 중심이나 report payload(메트릭 체인) 책임이 모호

## D. 단계 2 산출 목표 (실행 가능 체크리스트)

- [ ] `service_contracts` 기준으로 호출 계약 정리
- [x] UI 스레드로 들어오는 실패 경로를 `fail-closed` 정책으로 정리
  - 비교/캘리브레이션 결과 레이어 UID 불일치 즉시 실패
- [x] run_analysis/compare/calibration 에 대해 동일 요청/seed에서
  - layer contract hash
  - split manifest
  - 결과 레포트 hash
  를 반환하도록 최소 인터페이스 추가 검토
- [x] compare/top-change/캘리브레이션 실패를 각각 다른 에러 코드로 구조화
- [x] `analysis.py` 보고서에 `calibration_split` 메타데이터 추가
- [ ] 단계 2 완료 후 `docs/README`/`validation_protocol`와 동기화
