# 분석 품질 검증 행렬 (Layer C)

Updated: 2026-04-04

목적: 분석 파트가 “멋있게 보이기”보다 **안정적으로 해석 가능한지**를 점검합니다.

## 항목 A — 점수 안정성 (Score Stability)

검증 지표
- score boundedness (`0 <= score <= 1`)  
- aspect/water/slope 입력 변화에 대한 합리적 민감도
- monotonicity-like behavior for local perturbation

합격 기준
- 정규화/클리핑이 예측 가능한 방향으로 동작
- 극단값 입력에서도 오류 없이 값이 제한됨

## 항목 B — compare 정합성 (Compare Consistency)

검증 지표
- top-change row의 `delta`가 실제 점수 차이와 부호 일치
- 변경 feature UID 리스트에 누락/중복이 없는지
- selected/zoom 대상이 report와 일치

합격 기준
- top-change 요약과 지도 선택 동작의 핵심 의미가 충돌하지 않음
- 중복/누락이 있을 경우 fail-closed

## 항목 C — calibration 분리성 (Calibration Discipline)

검증 지표
- `fit`와 `evaluation` row 분리 여부
- validation disabled 케이스의 명시 메시지
- 성능 지표 표기에서 in-sample / held-out 구분

합격 기준
- in-sample 지표를 검증 성능처럼 과대해석하지 않음
- report notice에서 calibration 목적·제한이 공개

## 항목 D — 재현성 드리프트

검증 지표
- seed 고정 재실행 시 run manifest hash 핵심 필드 일치
- score drift tolerance 범위 내 편차
- fixture expected contract와 schema 일치

합격 기준
- seed 변경이 없어도 비교 가능한 범위를 벗어나지 않음
- 결과 drift 발생 시 허용치 + 원인 기록

## 실험 기록 권장 필드

- `case_id`
- `input_sha`
- `seed`
- `split_plan`
- `score_stability_notes`
- `top_change_overlap`
- `false_positive_notes`
- `false_negative_notes`
- `non-actionable_limitations`
