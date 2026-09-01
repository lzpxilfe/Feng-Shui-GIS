# Changelog

## 2026-09-02
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
