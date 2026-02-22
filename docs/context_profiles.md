# Context Profiles (Config-Driven)

파일:

- `feng_shui_gis/config/contexts.json`
- `feng_shui_gis/config/profiles.json`
- `feng_shui_gis/config/terms.json`
- `feng_shui_gis/config/analysis_rules.json`

핵심: 파라미터를 코드에서 분리해 하드코딩을 줄이고, 연구자가 설정 파일만 바꿔 실험할 수 있게 구성했습니다.

## 1) 지역/시대 컨텍스트

`contexts.json` 항목:

- 지역: `east_asia`, `korea`, `china`, `japan`, `ryukyu`, `southeast_asia`, `global_apm`
- 시대: `ancient`, `medieval`, `early_modern`, `modern`

주요 파라미터:

- `aspect_targets`, `aspect_sharpness`
- `water_distance_target`, `water_distance_sigma`
- `macro_radius_multiplier`, `micro_radius_multiplier`
- `hyeol_threshold`
- `weight_bias`, `term_bias`, `term_target_shift`

## 2) 분석 프로파일

`profiles.json` 항목:

- 기존: `general`, `tomb`, `house`, `village`, `well`, `temple`
- 확장: `urban_real_estate`, `global_apm`

각 프로파일은:

- `weights`
- `slope_target`, `slope_sigma`
- `tpi_target`, `tpi_sigma`
- 다국어 `label`

## 3) 풍수 용어/시각화

`terms.json` 항목:

- `term_labels`
- `radius_scales`
- `term_specs`
- `point_styles`, `line_styles`

즉, 용어 후보 추출 규칙과 두꺼운 선/점 심볼도 설정 파일에서 관리합니다.

## 4) 분석 규칙 상수

`analysis_rules.json` 항목:

- 샘플링 스케일/방위 간격
- 형세/혈/수렴도 점수의 목표값과 시그마
- 혈 후보 TPI 범위

이 파일로 DEM 연산 내부의 매직넘버를 별도 관리합니다.

## 5) 튜닝 절차

1. 설정 파일 복사본을 만들어 실험 세트 생성
2. 동일 DEM/유적 데이터에서 세트별 결과 산출
3. 회수율/정밀도 지표로 성능 비교
4. 최종 세트를 기준 브랜치에 반영
