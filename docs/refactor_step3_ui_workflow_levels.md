# 리팩토링 단계 3: UI 3층(Quick / Research / Developer) 정합성 정리

작성일: 2026-04-01  
목적: 현재 `dock_widget.py`에서 동작 중인 UI 흐름을 단계형으로 정리해, 기본 사용자에게는 최소 입력, 연구자에게는 진단/캘리브레이션/레포트 접근을 제공.

## 3.1 현재 상태 요약

- 기본/고급 토글은 `workflow_mode_combo`(`basic`, `expert`)로 존재.
- `advanced_options_button`을 통해 고급 영역 표시/숨김을 제어.
- 워크플로우 가이드:
  - `_workflow_checks` (현재 실행 준비 조건 계산)
  - `_refresh_progress_guide` (체크리스트/진행 퍼센트)
- 실행 버튼:
  - 분석 탭: `run_button`
  - 비교 탭: `compare_profiles_button`
  - 보정/용어추출/추가 버튼 존재
- 상태/진행 표시:
  - `workflow_progress`, `checklist_label`, `next_step_label`, `workflow_status_label`

## 3.2 3층 UX로 분해(안정화 설계)

### Quick layer
- 기본 진입면에서 표시
  - DEM/후보점/지역/반경 핵심 입력
  - 분석 실행(단일 버튼)
  - 기본 상태 가이드(진행/준비 상태)
- 숨김/축소 원칙: 추천/보정/비교/문헌/에러 상세는 기본 비노출

### Research layer
- `expert` 모드에서 추가 노출
  - 문헌/지역/시대 컨텍스트 확인
  - 보정 실행 및 결과 비교(기준/튜닝 비교)
- 용어/산줄기/수계 추출은 사용 목적별로 노출
- 선택 단계:
  1) 입력 확인
  2) 조건 충족 점검
  3) 실행/결과 레이어 점검
  4) 리포트/근거 확인

### Developer layer
- 운영자/디버깅 패널
  - 오류 카탈로그(어떤 실패인지)
  - CRS/레이어 스킵/좌표계 불일치 경고 로그
  - 실행 로그(작업 ID/태스크 ID/seed/컨트랙트)
  - 비교/보정/학습 분할 계약 스냅샷

## 3.3 단계 구현 체크리스트 (현재 레거시 대비)

- [ ] Quick/Research/Developer 패널의 UI 구성요소를 `QStackedWidget` + 탭/헤더로 명시적 분리
- [ ] 안내 텍스트는 정책 데이터(`workflow_state`)에서만 조합되도록 정리
- [ ] `compare`와 `calibration`은 Quick에서의 기본 실행 경로에서는 숨김 또는 one-click 가이드 경로로만 노출
- [ ] `run_profile_compare`/`run_calibration` 진입은 사용자 동의와 현재 상태(ready/not ready) 기반으로만 허용
- [ ] Dev layer는 기본 UI와 동일 레이어로 오버레이되지 않도록 `advanced`로 분리

## 3.4 다음 단계 제안

1. `dock_widget.py`에서 표시만 담당하고 정책은 `dock_widget_viewmodel.py`가 완전히 결정하도록 정리  
2. 비교/보정 결과는 최소 3개 상태 버킷으로 표시:
   - `Ready`
   - `Need action`
   - `Failed (with reason code)`
3. 실패 코드-메시지 맵을 UI status bar와 report popup에서 일치시킴
