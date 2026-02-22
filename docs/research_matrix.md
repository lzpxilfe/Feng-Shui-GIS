# Research Matrix (Region + Period + Archaeology)

기준일: 2026-02-22  
목적: 국가/시대별 풍수 해석 차이를 GIS 규칙으로 분리하기 위한 근거 정리

## 1) 지역·시대별 핵심 문헌

| 지역 | 시대 초점 | 출처 | 해석상 핵심 |
|---|---|---|---|
| 중국 | 진~당~명청(장묘/왕릉) | Han et al. 2021, Sustainability `13(15):8532` https://www.mdpi.com/2071-1050/13/15/8532 | Long/Sha/Shui/Xue를 GIS 지표로 정량화(AHP) |
| 중국 | 명~청 황릉 수문 맥락 | Sun et al. 2024, DOI `10.1038/s40494-024-01301-1` (CAS 보도: https://english.cas.cn/newsroom/research_news/life/202407/t20240708_675734.shtml) | 풍수 입지와 유역/물길 형성의 결합 |
| 한국 | 조선 왕릉 | UNESCO WHC (등재기준 관련 설명) https://whc.unesco.org/en/list/1319/ | 풍수 기반 입지(지형·방향·수계·의례축) |
| 한국 | 조선 전기 취락 지형 해석 | Kim 1991, *Jimbun Chiri* `43(1)` DOI `10.4200/jjhg1948.43.1_42` https://www.jstage.jst.go.jp/article/jjhg1948/43/1/43_1_42/_article | 풍수가 취락 지형 인식(형국도)과 연결됨 |
| 일본 | 수용사(에도까지) | Watanabe 2015, Estudos Japoneses `35` https://revistas.usp.br/ej/article/view/108036 | 중국 전래 풍수가 일본에서 과학/점술 체계와 융합 |
| 일본 | 중세 맥락 | Atsuko Koma 2014, Kyoto University Repository `史林 97(5)` https://repository.kulib.kyoto-u.ac.jp/dspace/handle/2433/193589 | 중세 일본 풍수 지리서의 전개와 문헌 수용 양상 |
| 일본(류큐/오키나와) | 근세~근현대 묘제 | Kinjo et al. 2024, Religions `15(2):203` https://www.mdpi.com/2077-1444/15/2/203 | 음양·풍수·현지 장묘 관행이 결합된 지역 변형 |
| 동아시아 공통 | 현대 경관학 관점 | Yue & Wang 2024, JoLA https://www.sciencedirect.com/science/article/pii/S1617138124000036 | 산수/보호-개방/방향 원리를 현대 공간분석으로 재해석 |
| 사찰 입지 | 근세/근대 사례 다수 | Bae et al. 2025, Land `14(5):1124` https://www.mdpi.com/2073-445X/14/5/1124 | 고도/경사/수계/접근성/가시성 복합 요인 |

## 2) 고고학 GIS 모델링 문헌

| 주제 | 출처 | 시사점 |
|---|---|---|
| 예측모델 체계 리뷰 | IJGI 2025 https://www.mdpi.com/2220-9964/14/4/133 | 변수의 문화권 의존성이 커서 지역 프리셋 필요 |
| 모델 검증 방법 | IJGI 2023 https://www.mdpi.com/2220-9964/12/6/228 | 전이 성능(지역/시대 이동) 검증이 필수 |
| ML 기반 APM 사례 | Cambridge 2023 https://www.cambridge.org/core/journals/latin-american-antiquity/article/machine-learning-in-archaeological-predictive-modelling-an-argentinian-case-study/A67A00E172BFE8458FBFF025B5A53DBD | 규칙 기반 결과를 후속 학습모델 피처로 활용 가능 |

## 3) 코드 반영: 국가/시대 분리

추가 파일:

- `feng_shui_gis/cultural_context.py`

반영 내용:

- 국가/지역: `east_asia`, `korea`, `china`, `japan`, `ryukyu`
- 시대: `ancient`, `medieval`, `early_modern`, `modern`
- 컨텍스트가 바꾸는 항목:
  - 향 점수 목표각/민감도
  - 수계 최적 거리/분산
  - 미시/거시 반경(형세 탐색 스케일)
  - `hyeol` 후보 임계치
  - 지표 가중치 편향(`form/long/water/aspect/...`)
  - 용어별 편향(`jusan`, `naesugu` 등)

결과 필드 확장:

- 점수 레이어: `fs_culture`, `fs_period`
- 용어 레이어: `culture`, `period`, `term_ko`

## 4) 이번 구현의 해석 범위

- 현재는 문헌의 질적 차이를 수치 파라미터로 1차 변환한 규칙 기반 모델
- “정답 판정”이 아니라 국가/시대별 가설 비교를 위한 연구 보조 레이어
- 발굴 기록/문헌 기록/유물 분포와 반드시 교차 검증 필요

## 5) 다음 고도화 우선순위

1. 왕조/시대 세분화 프리셋(예: 조선 전기/후기, 명/청 분리)
2. Viewshed 통합(사찰·봉수·왕릉 조망축)
3. GRASS `r.watershed` 기반 수구·입수 추정 보강
4. 현장 데이터로 파라미터 캘리브레이션(ROC/AUC, Precision-Recall)
