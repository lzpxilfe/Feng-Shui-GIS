# Code Review Notes

기준일: 2026-02-22  
범위: `feng_shui_gis` 전체

## Findings (Severity Order)

1. **High**: 핵심 파라미터/규칙이 코드 내부에 분산 하드코딩  
   - 위치: `analysis.py`, `cultural_context.py`, `dock_widget.py`  
   - 리스크: 연구 재현성/감사 추적성 저하, 파라미터 실험 시 코드 수정 필수  
   - 조치: JSON 설정 파일로 분리 (`config/*.json`) + 로더 모듈 추가

2. **Medium**: 용어 연결선에 0길이 선 생성 가능  
   - 위치: `analysis.py` `build_term_links`  
   - 리스크: 지도 렌더링 잡음, 후속 네트워크 분석 왜곡  
   - 조치: 시작/끝 좌표 동일 시 링크 생성 제외

3. **Medium**: 좌표계가 경위도(도 단위)일 때 거리/반경 기반 해석 오차 가능  
   - 위치: `plugin.py` 실행 루틴  
   - 리스크: 거리 스코어 왜곡  
   - 조치: 지리좌표계 감지 시 경고 메시지 추가

4. **Low**: UI 콤보 값 하드코딩(프로파일/문화권/시대)  
   - 위치: `dock_widget.py`  
   - 리스크: 확장 시 코드 변경 필요  
   - 조치: 설정파일 기반 동적 로딩

## Refactor Summary

- 설정 데이터 분리:
  - `feng_shui_gis/config/profiles.json`
  - `feng_shui_gis/config/terms.json`
  - `feng_shui_gis/config/contexts.json`
  - `feng_shui_gis/config/analysis_rules.json`
- 로더/카탈로그 추가:
  - `feng_shui_gis/config_loader.py`
  - `feng_shui_gis/profile_catalog.py`
- 컨텍스트 로직 재구성:
  - `feng_shui_gis/cultural_context.py`
- UI/분석 엔진을 설정 기반으로 전환:
  - `feng_shui_gis/dock_widget.py`
  - `feng_shui_gis/analysis.py`
- 안전장치 추가:
  - 지리좌표계 경고, 0길이 링크 필터
