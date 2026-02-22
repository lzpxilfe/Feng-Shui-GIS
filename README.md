# Feng Shui GIS (QGIS Plugin) v0.1.0

풍수 GIS는 DEM 기반 지형 해석을 중심으로, 풍수 연구에서 중요한 `맥(능선)`, `수계 흐름`, `혈/명당 후보`를 QGIS에서 재현하는 연구용 플러그인입니다.

## 핵심 개념

- 기본값은 **DEM + 수계 중심 해석**입니다.
- 수계 레이어가 없으면 **DEM 자동 수문 추출**을 수행합니다.
- 입지 점수(`fs_score`)는 **고급 분석(선택 모드)**로 분리했습니다.

## 주요 기능

1. 기본 지형 모드
- DEM에서 능선 네트워크를 추출하고 계층화:
  - `대간(daegan) / 정맥(jeongmaek) / 기맥(gimaek) / 지맥(jimaek)`
- DEM 또는 입력 수계를 바탕으로 수계 흐름 레이어 생성:
  - `main / secondary / branch / minor`
- 필요 시 풍수 용어 포인트/구조 연결선 추가:
  - 혈, 명당, 주산, 조종산, 청룡/백호, 수구, 입수, 안산/조산, 미사

2. 고급 분석 모드
- 후보지 포인트 + DEM(+수계)로 `fs_score` 계산
- 문화권/시대 컨텍스트 기반 파라미터 조정

3. 시각화
- 점/선 레이어 순서 자동 정리(점이 선 위)
- 중심 방사형 스포크가 아닌 구조형 연결(내/외, 전/후, 좌/우 단계)
- 상세 도움말 다이얼로그(워크플로우/심볼/레퍼런스 탭)

## 출력 레이어

- `*_fengshui_ridges`
  - `ridge_class`, `ridge_rank`, `strength`, `len`
- `*_fengshui_hydro` (자동 생성 시)
  - `stream_class`, `order`, `flow_acc`, `len`
- `*_fengshui_terms` (상세 옵션)
  - `term_id`, `term_ko`, `score`, `culture`, `period`
- `*_fengshui_terms_links` (상세 옵션)
  - `term_id`, `term_ko`, `score`, `culture`, `period`
- `*_fengshui` (고급 분석)
  - `fs_score`, `fs_note`, `fs_culture`, `fs_period`, `fs_model` 등

## 빠른 시작

1. QGIS에서 플러그인 로드
2. DEM 선택
3. 기본 지형 탭에서 `지형 흐름/맥 추출` 실행
4. 필요 시 `풍수 용어 포인트/구조 연결선` 옵션 활성화
5. 후보지 데이터가 있으면 고급 분석 탭에서 `분석 실행`

## 데이터/좌표계 권장

- DEM: 투영 좌표계(미터 단위, UTM/TM) 권장
- 수계: 라인/폴리곤 입력 가능(없으면 DEM 자동 추출)

## 설정 파일(하드코딩 최소화)

- `feng_shui_gis/config/contexts.json`
- `feng_shui_gis/config/profiles.json`
- `feng_shui_gis/config/terms.json`
- `feng_shui_gis/config/analysis_rules.json`

연구자는 코드 수정 없이 설정 파일만으로 가중치/반경/용어 규칙을 조정할 수 있습니다.

## 연구 문헌 및 노트

- `docs/research_matrix.md`
- `docs/context_profiles.md`
- `docs/regional_period_notes.md`
- `docs/code_review.md`

## 주의

- 본 플러그인은 연구 보조 도구입니다.
- 자동 산출은 “최종 판정”이 아니라 “후보 가설 지도”이며, 문헌·발굴·현장 검증과 함께 해석해야 합니다.

---

## Brief (EN)

Feng Shui GIS prioritizes DEM-first landscape reading (ridges + hydro) and keeps site scoring as an optional advanced workflow.  
It outputs hierarchical ridge lines, hydro-flow lines, and optional Feng Shui term layers for archaeological interpretation.

## 简介 (ZH)

本插件以 DEM 地形解读为核心，优先生成山脊层级与水系流线，并将选址评分作为可选高级流程。  
适用于考古与历史地理研究中的风水景观对比分析。

## 概要 (JA)

本プラグインは DEM を中心に、まず山脈の階層と水系流線を抽出し、立地点数評価は任意の高度解析として分離しています。  
考古・歴史地理研究向けの比較可能な地形解釈を提供します。
