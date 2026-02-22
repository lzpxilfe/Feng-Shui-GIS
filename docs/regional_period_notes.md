# Regional/Period Notes for Interpretation

기준일: 2026-02-22  
이 문서는 `cultural_context.py` 파라미터를 해석하기 위한 연구 노트입니다.

## 국가/지역 차이

### China
- 장묘 풍수 연구에서 `Long/Sha/Shui/Xue` 구조를 정량화하는 경향이 강함.
- 왕릉/황릉 맥락에서 대규모 지형 스케일과 수문 체계가 강조됨.
- 참고:
  - https://www.mdpi.com/2071-1050/13/15/8532
  - https://doi.org/10.1038/s40494-024-01301-1

### Korea
- 배산임수, 좌청룡·우백호, 안산/조산 체계가 왕릉·취락 입지 해석에 핵심.
- 취락 지도/형국도의 지형 인식이 풍수와 결합되어 나타남.
- 참고:
  - https://whc.unesco.org/en/list/1319/
  - https://www.jstage.jst.go.jp/article/jjhg1948/43/1/43_1_42/_article

### Japan
- 중국 전래 이후 일본에서는 풍수가 음양도/방위 금기 체계와 결합해 변형됨.
- 방향 체계의 엄격성이 지역/시대별로 달라져 해석 민감도를 낮춰볼 필요가 있음.
- 참고:
  - https://revistas.usp.br/ej/article/view/108036
  - https://repository.kulib.kyoto-u.ac.jp/dspace/handle/2433/193589

### Ryukyu/Okinawa
- 가문 묘제와 결합된 지역 변형이 강하며 해안/수계 조건의 영향이 큼.
- 수구/입수 관련 지표를 상대적으로 높게 보는 실험적 가정이 타당.
- 참고:
  - https://www.mdpi.com/2077-1444/15/2/203

### Southeast Asia
- 현대 도시 맥락에서는 풍수 요인이 부동산 가치/선호에 영향을 보인다는 실증 연구가 존재.
- 입수/수구 계열(수문 접근), 방향 계열(향) 지표를 상대적으로 강화하는 설정을 실험.
- 참고:
  - https://www.emerald.com/insight/content/doi/10.1108/PM-01-2020-0001/full/html
  - https://doi.org/10.1016/j.habitatint.2019.102068

### Global APM baseline
- 지역 고유 풍수 규칙이 불명확한 경우, 고고학 예측모델 공통 변수 중심의 중립 베이스라인이 유용.
- 경사/수계/상대고도/수렴도 중심으로 보수적으로 설정.
- 참고:
  - https://www.mdpi.com/2220-9964/14/4/133
  - https://www.mdpi.com/2220-9964/12/6/228

## 시대 차이(분석 가설)

### Ancient
- 방어/지형 지배성(주산·조종산) 가중치를 높임.
- 광역 지형 스케일을 더 크게 샘플링.

### Medieval
- 산줄기와 형세 균형을 중시하는 과도기 가정.

### Early modern
- 의례화/제도화된 입지 규범 반영(방향성 민감도 소폭 강화).

### Modern/Contemporary
- 토지 이용 변화와 수문 인프라 영향 고려(수계/수렴도 가중치 상대 증가).

## 구현 상 주의

- 위 내용은 문헌의 질적 논의를 DEM 규칙으로 1차 번역한 것.
- 지역·시대별 진짜 규칙은 유적 검증 데이터로 재보정해야 함.
