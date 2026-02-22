# Context Profiles (Editable Rules)

파일: `feng_shui_gis/cultural_context.py`

이 플러그인은 국가/시대 차이를 고정 코드가 아니라 프로파일 파라미터로 분리합니다.

## 문화권 프로파일

| key | 의미 |
|---|---|
| `east_asia` | 동아시아 공통 기본값 |
| `korea` | 한국 풍수/비보풍수 맥락 |
| `china` | 중국 장묘·형세 중심 맥락 |
| `japan` | 일본 수용형 풍수(방위/형세 혼합) |
| `ryukyu` | 류큐/오키나와 지역 변형 |

주요 파라미터:

- `aspect_targets`: 반구별 목표 사면 방향
- `aspect_sharpness`: 방향 엄격도
- `water_distance_target`, `water_distance_sigma`: 수계 거리 선호 분포
- `macro_radius_multiplier`, `micro_radius_multiplier`: 지형 탐색 스케일
- `hyeol_threshold`: 혈 후보 임계치
- `weight_bias`: 점수 항목 가중치 편향
- `term_bias`: 용어별 점수 보정
- `term_target_shift`: 용어 고도차 목표 이동량

## 시대 프로파일

| key | 의미 |
|---|---|
| `ancient` | 고대 |
| `medieval` | 중세 |
| `early_modern` | 근세 |
| `modern` | 근현대 |

시대 프로파일은 문화권 프로파일 위에 가산/배율로 적용됩니다.

## 튜닝 방법

1. `cultural_context.py`에서 문화권/시대 파라미터 수정
2. 동일 DEM에서 프로파일만 바꿔 결과 비교
3. 실제 유적 포인트의 회수율/정밀도 기준으로 재조정
