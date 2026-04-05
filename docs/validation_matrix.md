# 4-Layer Validation Matrix (Software / User / Analytical / Research)

Updated: 2026-04-04

이 문서는 플러그인의 검증을 한 번에 4개 게이트로 정리한 기준입니다.  
목표는 “테스트 수가 많아지는 것”이 아니라 **실패를 `어디서`로 분류할지 바로 알 수 있는 체계**를 만드는 것입니다.

## Gate A — 소프트웨어 신뢰성 (A: Engineering Reliability)

목적
- 재현 가능한 산출물 계약이 깨지지 않고, 실패가 조용히 침묵하지 않고 종료되며, run manifest / artifact가 항상 생성되는지 확인.

패스 조건
- plugin enable, dock open, analysis/compare/calibration 진입에서 기본 예외 경로가 fail-closed로 처리됨
- `RunManifest` 및 report payload 필수 키가 계약에 맞게 존재
- 동일 입력/동일 seed에서 run-id만 제외한 핵심 메타 정보가 안정적
- 실패/오류는 코드로 매핑 가능한 error code로 수집됨

필수 점검 항목
- `tests/test_service_contracts.py`
- `tests/test_failure_paths.py`
- `tests/test_reproducibility_stability.py` (기존)
- `tools/run_asset_smoke.py` dry-run 계약
- `tools/run_headless_smoke.py` dry-run 계약

## Gate B — 사용자 사용성 (B: Product Usability)

목적
- 초보자가 “샘플 프로젝트로 5~10분 안에” 결과를 획득하고, 경고 메시지가 이해 가능한지 확인.

패스 조건
- `docs/first_run_guide.md`만 보고도 기본 실행이 가능한지
- bad CRS / no water / no site 경고가 조치 지침과 함께 표시되는지
- cancel/rerun / language restore 동작이 인터페이스에서 안정적으로 동작하는지

필수 점검 항목
- `docs/first_run_guide.md`
- `docs/troubleshooting.md`
- `tests/test_user_flow_smoke.py`

## Gate C — 분석 일관성 및 설명 가능성 (C: Analytical Quality)

목적
- score, compare, calibration 결과가 “의미론적 오해” 없이 일관되게 설명되는지 확인.

패스 조건
- score 단조성/클리핑 규칙이 지켜짐 (`0~1`, 이상치가 정리됨)
- calibration split misuse(학습/평가 행 불일치) 탐지 및 fail-closed
- compare top-change 정렬/선택/보고문구가 일관

필수 점검 항목
- `tests/test_score_behavior.py`
- `tests/test_compare_behavior.py`
- `tests/test_calibration_behavior.py`
- `tests/test_reproducibility_stability.py`

## Gate D — 유적 사례 유효성 (D: Archaeological Validity)

목적
- 실제 케이스에서 성능 지표와 오답 케이스 해석이 문서화되는지 확인.

패스 조건
- 최소 3개 benchmark case 정의 및 1회 이상 실행 기록
- known positive/negative/neutral 분류와 miss-hypothesis가 문서화
- “어떤 것을 말할 수 없나”가 항상 포함

필수 점검 항목
- `benchmarks/case_001_korea_tomb.md`
- `benchmarks/case_002_region_mixed.md`
- `benchmarks/case_003_landscape_baseline.md`
- `docs/benchmark_plan.md`
- `docs/analytical_validation_matrix.md`

## Gate 상태(예시)

| Gate | 상태 | 판정 근거 |
|---|---|---|
| A | ☐ open | 계약/재현성 테스트 실행 후 업데이트 |
| B | ☐ open | 사용자 시나리오 기록 후 업데이트 |
| C | ☐ open | score/compare/calibration 테스트 결과 반영 |
| D | ☐ open | Benchmark case별 요약 작성 후 업데이트 |

## 실패 레이어 태깅

- `1` → Layer A (software)
- `2` → Layer B (usability)
- `3` → Layer C (analytical)
- `4` → Layer D (research)

실패 메시지와 이슈에서 레이어 태그를 붙여, 회귀 수정 우선순위를 고정합니다.
