# Changelog

## 2026-09-02
- **[동작 변경] `fs_conf` → `fs_cover`** — 측정하지 않은 신뢰도 표기 제거
  - 실제 계산은 `(값이 나온 지표의 가중치 합) / (전체 가중치 합)`, 즉 **입력 충족률**이었음
  - 지표가 전부 계산되기만 하면 DEM 품질·검증 여부와 무관하게 1.0 표시
  - 맵팁에서 점수와 동일한 `strong/good/moderate/weak` 밴드가 붙어 품질 등급처럼 보였음 → 밴드 제거
  - 라벨을 `지표 충족률` / `Indicator coverage`로 정정, 사용 안내에서 점수와 분리해 설명
  - `fs_missing` 필드 추가: 산출되지 않은 지표 목록
  - 점수가 부분 지표로 재정규화된 경우 `fs_reason`에 명시
  - `profile_confidence` → `profile_indicator_coverage`, `missing_indicator_keys` 추가
  - 저장된 스타일·표현식에서 `fs_conf`를 쓰던 경우 `fs_cover`로 바꿔야 함
- 조망(시선) 분석 추가 — 안산·조산이 실제로 보이는지 판정
  - `analysis_visibility.py` 신설: 지형 단면 기반 시선 판정 (QGIS 비의존, 순수 기하)
  - 지구 곡률·대기 굴절 반영(k=0.13), 관측자 눈높이 1.7m 기본
  - `sample_sight_profile`: 혈-대상 직선 DEM 단면 표집(최대 64점, 원거리도 비용 일정)
  - 용어 레이어에 `visible` / `los_clear` 필드 추가, `reason_ko`에 조망 결과 기술
  - **점수(`fs_score`)는 변경하지 않음** — 근거 확보 전까지 사실만 기록
  - `docs/visibility_analysis.md` 추가
- **[동작 변경] 능선 등급 라벨 정정** — 산경표 고유명사 오용 제거
  - `major`/`minor`는 분석범위 내 상위 30% 백분위 분할인데 `대간·정맥`/`기맥·지맥`으로 표시되고 있었음
  - 범위를 바꾸면 같은 능선의 등급이 바뀌므로 산경표 판정으로 읽힐 수 없는 값
  - 라벨을 `주능선(분석범위 상위)` / `가지능선`으로 정정 (필드값 `major`/`minor`는 유지)
  - 능선 `reason_ko`에 "산경표 대간·정맥 판정이 아님" 명시
  - `config/ridge_classes.json` 신설: 계산 등급과 산경표 참조 체계(1대간·1정간·13정맥)를 분리 기록
  - `identified_by_this_plugin=false` 고정, 검증기가 `true` 변경을 거부
  - `docs/korean_ridge_system.md` 추가
- 중국 좌표계 정합성 (`china_geodesy`)
  - GCJ-02 / BD-09 / WGS84 상호 변환 추가 (공개 기준점 대조 검증)
  - 분석 범위가 중국 경내일 때 좌표계 혼동 시 편이량(m)과 DEM 셀 환산값을 경고
  - 경위도 DEM 거부 시 해당 범위의 CGCS2000 3도대 가우스-크뤼거 EPSG 코드를 구체적으로 제시
  - 인접국(한반도·일본) 오탐 억제 게이트 분리: GCJ-02 알고리즘 적용 범위와 사용자 경고 범위를 구분
  - `docs/china_data_guide.md` 추가
  - `plugin.py`의 라벨 언어 `ko`/`en` 하드코딩 제거
- 중국어 용어 체계 도입 (형세파 범위 한정)
  - `terms.json`에 간체·번체·병음 라벨과 `label_languages` 선언 추가
  - `term_ontology` 신설: 유파(形勢派/理氣派) 범위, 대응 등급(직접/근사/논쟁적), 이체어, 차이 설명 note
  - 이기파(理氣派)를 "미구현"이 아니라 **범위 밖**으로 명시
  - 라벨 언어 선택을 카탈로그 기반으로 전환, `ko`/`en` 하드코딩 7곳 제거
  - `zh_CN`/`zh-TW` 등 지역 변형 코드가 한국어로 되돌아가던 문제 수정
  - 구조 연결선 레이어에 언어 중립 표시 필드 `term_lbl`/`src_lbl`/`dst_lbl` 추가
  - `docs/chinese_terminology.md` 대응표와 주의사항 문서 추가
  - `tests/test_term_ontology_contract.py`: 설명 없는 등가 주장을 설정 로드 단계에서 거부
- CI 게이트 복구
  - `metadata.txt`의 빈 `tracker` 값 복구 (release guard 실패 원인)
  - README에 support bundle 라벨 복구, sample project README의 로컬 절대경로 제거
  - `test_compare_contracts`가 `sys.modules`에 남기던 스텁을 정리해 테스트 10개 추가 수집

## 2026-04-01
- 플러그인 스토어 공개 기준 문서/metadata 정리
  - heuristic / not predictive / calibration limitation / projected CRS 권고를 metadata와 README에 통일
  - `docs/tested_versions.md` 추가
  - first-run guide를 초심자 5단계 경로 중심으로 재구성
  - sample project README에 expected outputs 안내 추가
  - release checklist / support bundle guide / bug report template 강화

## 2026-03-31
- README에 사용성 중심 가독성 개편
  - 빠른 시작(1분/5분) 섹션 추가
  - 3단계 작업 흐름과 스크린샷 예시용 설정 순서 템플릿 추가
  - requirements 및 changelog 링크 블록 정리

## 2026-03-31 이후 이어지는 기록
- 기능 변경 및 버그 수정은 동일 형식으로 누적 정리 예정
  - 버전 태그/릴리스가 확정되면 항목으로 반영
