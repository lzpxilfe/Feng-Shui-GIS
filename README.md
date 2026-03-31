# Asian Landscape Reader (Feng Shui GIS)

> A QGIS plugin for **terrain-first** historical landscape reading with transparent context-aware assumptions.

## 핵심 목표 / What this plugin is for

- 지형(`DEM`)에서 산맥 골격, 수계, 수평·수직 관계를 먼저 읽는다.
- 후보지 평가(`fs_score`)는 **별도의 고급 단계**로 수행한다.
- 지역/시대별 설정은 근거를 남기고, 기본값은 검증 가능한 범위를 유지한다.
- 동일 파이프라인에서 연구 재현성(리포트, 설정, 버전)을 보장한다.

이 플러그인의 목표는 “한 번에 끝내는 신뢰도 높은 점수 산출”이 아니라,
**단계별로 분석 책임을 보존하는 의사결정 워크플로**를 제공하는 것입니다.

## 3단계 워크플로 (기본 모드)

1. **Input (입력 준비)**
   - DEM, 수계(선택), 후보지(선택) 레이어 지정
   - 반구/언어 설정
2. **Terrain Extraction (지형 추출)**
   - 지형 구조(능선/수계) 생성
   - 용어 점을 필요한 경우에만 생성
3. **Evaluation / Interpretation (해석 및 점수)**
   - 필요 시 후보지 점수 계산
   - 캘리브레이션 프로파일 비교, 리포트, 변경 요약 확인

## 왜 이 구조인가?

- DEM-only로 시작해야 결과가 과적합되지 않는다.
- 지역/시대 설정은 `Advanced Context`에서 선택적으로 켜서, 비교 실험이 가능해야 한다.
- 실험적 프로파일은 기본값에서는 숨기고, 사용자가 명시적으로 활성화할 때만 사용한다.

## 플러그인 구성

- `extract`
  - 라스터 DEM에서 능선/유역 기반 구조 추출
  - 수계 레이어 미존재 시 자동 대체 수계 사용
- `terms`
  - 산단 구조 용어 포인트/연결선(옵션)
- `scoring`
  - 후보지 점수, 이유(`reason`, `fs_reason`) 포함 출력
- `context`
  - 일반 모드(중립), 고급 모드(지역/시대) 전환
  - `contexts.json` 기반 컨텍스트 근거 브라우징
- `calibration`
  - 로컬 보정(임계치/프로파일) + 추천 프로파일 생성
  - 추천·기준 비교 + 변경 리포트

## 문서 링크

- `docs/context_profiles.md` (컨텍스트 정책)
- `docs/reference_audit.md` (근거 추적)
- `docs/research_matrix.md` (실험 설계)
- `docs/regional_period_notes.md` (지역/시대 보정 노트)
- `docs/researcher_quickstart.md` (연구 워크플로)
- `docs/validation_protocol.md` (검증 체크)

## 사용 제한(정직한 전제)

- 산·수계 자동추출은 좋은 DEM 품질일수록 안정적이다.
- 지역/시대 컨텍스트는 **초기 우선순위**일 뿐, 현장 조사와 독립 검증을 대체하지 못한다.
- 실험적 프로파일은 탐색 목적 전용이다.

## 빠른 시작

1. 패널에서 DEM 레이어를 지정
2. 수계 레이어 지정(없으면 자동 수계 사용)
3. 후보지 포인트(있으면) 지정
4. `지형 구조 추출` 실행
5. 필요 시 용어 점·해석 탭으로 이동
6. 지역/시대 보정이 필요하면 `고급 설정`에서 활성화
