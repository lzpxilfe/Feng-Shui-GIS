# Benchmark Case 운영 계획 (Layer D)

Updated: 2026-04-04

이 문서는 최소 3개 케이스를 시작점으로 운영할 연구 검증 레이어입니다.

현재 researcher-beta 기준의 canonical real-data case는
`benchmarks/case_001_korea_tomb.md`의 공주 백제 cluster-level descriptive benchmark입니다.

## 케이스 구조

각 케이스는 다음 필드를 갖습니다.

- `case_id`
- `title`
- `region`
- `period`
- `site_type`
- `DEM source / resolution / CRS`
- `Water source`
- `Known positives`
- `Known negatives`
- `Neutral context / Context profile / Calibrated profile`
- `Expected interpretation bias`
- `run manifest`
- `top-k hit expectations`
- `known limitations`

## 실행 프로토콜

1. 동일 데이터셋을 neutral → context → calibration 순으로 최소 1회 실행
2. compare는 `context_vs_neutral`, `calibrated_vs_context` 두 쌍을 고정 실행
3. 각 설정의 결과 레이어, compare summary, report를 저장
4. compare 결과를 기존 케이스 결과와 누적 비교
5. false positive/negative를 유형별로 분류:
   - DEM 품질 이슈
   - hydro sourcing 이슈
   - 모델 파라미터 오버피팅
   - 문헌-현장 불일치

## 산출물

- `case report` (요약)
- `score delta summary`
- `run manifest hash`
- `known 오판 유형 태그`

## 실패 분류 기준

- A: 분석/실행 실패 (Layer A)
- B: 사용성 실패 (Layer B)
- C: 분석 품질 실패 (Layer C)
- D: 연구 유효성 실패 (Layer D)

문서에는 레이어 태그를 포함해, 다음 작업 우선순위를 고정합니다.
