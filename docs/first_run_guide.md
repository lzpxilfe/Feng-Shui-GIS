# ⚡ 5분 빠른 시작 가이드

`five-step first run`

1. Load the DEM.
2. Select a water layer, or use auto-hydro.
3. Select the candidate point layer.
4. Run terrain extraction and then site analysis.
5. Check the result layers and the generated report artifacts.

Representative use cases:

- quick terrain reading
- research compare / calibration
- support bundle repro sharing

1. QGIS에서 플러그인을 실행하고, `Asian Landscape Reader (Feng Shui GIS)` 패널을 엽니다.
2. `DEM` 레이어를 선택합니다.
3. `water` 레이어가 있으면 지정하고, 없으면 `auto-hydro`를 켭니다.
4. `sites`(포인트/폴리곤) 레이어를 지정합니다.
5. `Analyze` 버튼으로 분석을 실행하고, 결과 레이어/리포트를 확인합니다.

## 결과가 안 나올 때 가장 먼저 확인할 것

- DEM/사이트/수계의 CRS가 호환되는지
- DEM이 degree(경위도) 단위면 미터 기반 투영 CRS로 다시 변환했는지
- 수계 레이어가 없어도 auto-hydro가 동작하는지
- 좌표계·레이어 타입 경고 메시지를 그대로 따라 재실행했는지

## 참고 순서(권장)

- 우선 `analysis`만 성공시키고
- 다음에 `compare`
- 마지막으로 `calibration`
- 보고서와 manifest가 생성되는지 체크

## 실데이터로 바로 돌리기

반복 실험용 케이스 폴더를 먼저 만들면, 이후에는 같은 구조로 데이터만 갈아끼우며 점검할 수 있습니다.

예시:

```bash
python3 tools/setup_study_case.py \
  user_cases/gongju_baekje \
  --dem /path/to/sample-dem.tif \
  --sites /path/to/tomb-sites.shp \
  --water /path/to/water.shp \
  --title "Gongju Baekje study" \
  --profile tomb
```

- 실행하면 `case.json`, `README.md`, `inputs/`가 생성되고, 현재 셸에서 QGIS 런타임이 보이는지도 함께 알려줍니다.
- 폴리곤 사이트 레이어를 넣으면 centroid 기반 해석 경고를 같이 출력합니다.

기존 픽스처 스모크가 필요하면 `tests/fixtures/` 케이스에도 데이터를 반영할 수 있습니다.

예시:

```bash
python3 tools/prepare_smoke_case_inputs.py \
  tests/fixtures/clear_hydro_case \
  --dem /path/to/sample-dem.tif \
  --sites /path/to/tomb-sites.shp \
  --water /path/to/water.shp
```

- SHP는 `.shp` 단독이 아니라 `.shx`, `.dbf`, `.prj`(가능하면 `.cpg`)를 함께 둬야 합니다.
- 입력 반영 후 `python3 tools/run_asset_smoke.py` 를 실행하면 각 케이스의 `inputs_ready` 상태를 확인할 수 있습니다.
