# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QLocale

_LANGUAGE_OVERRIDE = None

_MESSAGES = {
    "en": {
        "plugin_title": "Asian Landscape Reader",
        "menu_title": "Asian Landscape Reader",
        "panel_title": "Asian Landscape Reader",
        "panel_subtitle": "Read East Asian and cross-regional terrain form before scoring: ridges, hydro structure, and historical settlement clues.",
        "sites_label": "Site points",
        "dem_label": "DEM raster",
        "water_label": "Water layer (optional)",
        "hemisphere_label": "Hemisphere",
        "hemisphere_north": "Northern",
        "hemisphere_south": "Southern",
        "model_label": "Reading profile",
        "model_general": "General terrain",
        "model_tomb": "Ritual/Burial terrain",
        "model_house": "Settlement / Domestic landscape",
        "model_village": "Village / Rural landscape",
        "model_well": "Well",
        "model_temple": "Temple",
        "culture_label": "Region profile (East Asian focus)",
        "culture_east_asia": "East Asia baseline",
        "culture_korea": "Korea",
        "culture_china": "China",
        "culture_japan": "Japan",
        "culture_ryukyu": "Ryukyu/Okinawa",
        "period_label": "Historical period",
        "period_ancient": "Ancient",
        "period_medieval": "Medieval",
        "period_early_modern": "Early modern",
        "period_modern": "Modern/Contemporary",
        "tab_landscape": "Terrain Reading",
        "tab_analysis": "Scoring / Interpretation",
        "landscape_desc": "First extract terrain skeleton (ridges + hydrography) from DEM, then add spatial-hierarchy terms when needed.",
        "analysis_desc": "Optional scoring mode for settlement/ritual candidate points and historical location comparison.",
        "auto_hydro_label": "If water layer is missing, derive hydro network from DEM automatically",
        "include_terms_label": "Also create terrain structure terms and links",
        "analysis_auto_hydro_label": "Use DEM-derived hydro network when water layer is missing",
        "extract_landscape_button": "Extract Landscape Structure",
        "help_button": "Detailed Help",
        "help_dialog_title": "Asian Landscape Reader - Detailed Guide",
        "help_tab_overview": "Workflow",
        "help_tab_symbols": "Symbols",
        "help_tab_references": "References",
        "run_button": "Run Analysis",
        "extract_terms_button": "Extract DEM Terms",
        "status_idle": "Choose layers, then run analysis.",
        "status_running": "Analysis in progress...",
        "status_terms_running": "Extracting DEM Feng Shui terms...",
        "status_done": "Analysis completed.",
        "warn_missing_layers": "Select site points and DEM first.",
        "warn_dem_required": "Select DEM first.",
        "warn_geographic_crs": "DEM CRS is geographic (degrees). Use projected CRS in meters for reliable distances.",
        "warn_failed": "Analysis failed",
        "ok_finished": "Created scored layer",
        "ok_terms_finished": "Created Feng Shui term layer",
        "ok_landscape_finished": "Created landscape flow layers",
    },
    "ko": {
        "plugin_title": "아시아 고대공간 리더",
        "menu_title": "아시아 고대공간 리더",
        "panel_title": "아시아 고대공간 리더",
        "panel_subtitle": "DEM으로 지형의 능선·수계 골격을 먼저 읽고, 필요 시 후보지 점수까지 이어가는 고고·공간지리 도구입니다.",
        "sites_label": "후보지 포인트",
        "dem_label": "DEM 래스터",
        "water_label": "수계 레이어(선택)",
        "hemisphere_label": "반구",
        "hemisphere_north": "북반구",
        "hemisphere_south": "남반구",
        "model_label": "공간해석 프리셋",
        "model_general": "일반 지형",
        "model_tomb": "의식/무덤 지형",
        "model_house": "주거·정착지",
        "model_village": "마을/촌락",
        "model_well": "우물",
        "model_temple": "사찰",
        "culture_label": "지역 프로파일(동아시아 중심)",
        "culture_east_asia": "동아시아 기본",
        "culture_korea": "한국",
        "culture_china": "중국",
        "culture_japan": "일본",
        "culture_ryukyu": "류큐/오키나와",
        "period_label": "시대 구분",
        "period_ancient": "고대",
        "period_medieval": "중세",
        "period_early_modern": "근세",
        "period_modern": "근현대",
        "tab_landscape": "지형 읽기",
        "tab_analysis": "해석/채점",
        "landscape_desc": "기본 모드: DEM에서 능선 계층과 수계 구조를 먼저 읽어 정형화한 뒤, 필요할 때만 용어 구조를 덧씌웁니다.",
        "analysis_desc": "후보지 포인트가 있을 때만 정착지·의식/무덤 후보에 대해 점수 기반 비교분석(fs_score)을 실행합니다.",
        "auto_hydro_label": "수계 레이어가 없으면 DEM 기반 자동 수문 추출 사용",
        "include_terms_label": "지형 구조 용어 포인트·연결선도 함께 생성",
        "analysis_auto_hydro_label": "분석 시 수계가 없으면 DEM 자동 수문 추출 사용",
        "extract_landscape_button": "지형 구조 추출",
        "help_button": "상세 도움말",
        "help_dialog_title": "아시아 고대공간 리더 - 상세 가이드",
        "help_tab_overview": "워크플로우",
        "help_tab_symbols": "심볼",
        "help_tab_references": "레퍼런스",
        "run_button": "분석 실행",
        "extract_terms_button": "DEM 용어 추출",
        "status_idle": "레이어를 선택하고 분석을 실행하세요.",
        "status_running": "분석 중...",
        "status_terms_running": "DEM 기반 풍수 용어를 추출하는 중...",
        "status_done": "분석 완료.",
        "warn_missing_layers": "후보지와 DEM을 선택하세요.",
        "warn_dem_required": "DEM을 선택하세요.",
        "warn_geographic_crs": "DEM 좌표계가 경위도(도 단위)입니다. 거리 신뢰성을 위해 미터 투영 좌표계를 권장합니다.",
        "warn_failed": "분석 실패",
        "ok_finished": "점수 레이어가 생성되었습니다",
        "ok_terms_finished": "풍수 용어 레이어가 생성되었습니다",
        "ok_landscape_finished": "지형 흐름 레이어가 생성되었습니다",
    },
    "zh": {
        "plugin_title": "Feng Shui GIS",
        "menu_title": "Feng Shui GIS",
        "panel_title": "Feng Shui GIS",
        "panel_subtitle": "优先根据 DEM 和水系解读地形，仅在需要时计算高级选址评分。",
        "sites_label": "候选点图层",
        "dem_label": "DEM 栅格",
        "water_label": "水系图层（可选）",
        "hemisphere_label": "半球",
        "hemisphere_north": "北半球",
        "hemisphere_south": "南半球",
        "model_label": "考古预设",
        "model_general": "通用",
        "model_tomb": "墓葬",
        "model_house": "居住",
        "model_village": "村落",
        "model_well": "水井",
        "model_temple": "寺庙",
        "culture_label": "区域/国家预设",
        "culture_east_asia": "东亚基准",
        "culture_korea": "韩国",
        "culture_china": "中国",
        "culture_japan": "日本",
        "culture_ryukyu": "琉球/冲绳",
        "period_label": "历史时期",
        "period_ancient": "古代",
        "period_medieval": "中世",
        "period_early_modern": "近世",
        "period_modern": "近现代",
        "help_dialog_title": "Feng Shui GIS - 详细指南",
        "run_button": "运行分析",
        "extract_terms_button": "提取 DEM 术语",
        "status_idle": "选择图层后开始分析。",
        "status_running": "分析进行中...",
        "status_terms_running": "正在提取 DEM 风水术语...",
        "status_done": "分析完成。",
        "warn_missing_layers": "请先选择候选点和 DEM 图层。",
        "warn_dem_required": "请先选择 DEM 图层。",
        "warn_geographic_crs": "DEM 为地理坐标系（度）。为保证距离可靠，建议使用米制投影坐标系。",
        "warn_failed": "分析失败",
        "ok_finished": "已创建评分图层",
        "ok_terms_finished": "已创建风水术语图层",
        "ok_landscape_finished": "已创建地形流线图层",
    },
    "ja": {
        "plugin_title": "Feng Shui GIS",
        "menu_title": "Feng Shui GIS",
        "panel_title": "Feng Shui GIS",
        "panel_subtitle": "DEM と水系を優先して地形を読み、必要な場合にのみ高度な立地スコアを計算します。",
        "sites_label": "候補地点ポイント",
        "dem_label": "DEM ラスター",
        "water_label": "水系レイヤー（任意）",
        "hemisphere_label": "半球",
        "hemisphere_north": "北半球",
        "hemisphere_south": "南半球",
        "model_label": "考古プリセット",
        "model_general": "一般",
        "model_tomb": "墳墓",
        "model_house": "住居",
        "model_village": "集落",
        "model_well": "井戸",
        "model_temple": "寺院",
        "culture_label": "地域プロファイル",
        "culture_east_asia": "東アジア基準",
        "culture_korea": "韓国",
        "culture_china": "中国",
        "culture_japan": "日本",
        "culture_ryukyu": "琉球/沖縄",
        "period_label": "時代区分",
        "period_ancient": "古代",
        "period_medieval": "中世",
        "period_early_modern": "近世",
        "period_modern": "近現代",
        "help_dialog_title": "Feng Shui GIS - 詳細ガイド",
        "run_button": "解析実行",
        "extract_terms_button": "DEM 用語抽出",
        "status_idle": "レイヤーを選択して解析を実行してください。",
        "status_running": "解析中...",
        "status_terms_running": "DEM 由来の風水用語を抽出中...",
        "status_done": "解析が完了しました。",
        "warn_missing_layers": "候補地と DEM を選択してください。",
        "warn_dem_required": "DEM を選択してください。",
        "warn_geographic_crs": "DEM が地理座標系（度）です。距離精度のためメートル系投影座標を推奨します。",
        "warn_failed": "解析失敗",
        "ok_finished": "スコア付きレイヤーを作成しました",
        "ok_terms_finished": "風水用語レイヤーを作成しました",
        "ok_landscape_finished": "地形フローレイヤーを作成しました",
    },
}


def _normalize_language_code(code):
    if code is None:
        return None
    normalized = str(code).strip().split("_", maxsplit=1)[0].lower()
    if normalized in _MESSAGES:
        return normalized
    return None


def _language_code():
    override = _normalize_language_code(_LANGUAGE_OVERRIDE)
    if override is not None:
        return override
    # Prefer system locale when available, then fall back to English.
    code = _normalize_language_code(QLocale.system().name())
    if code is not None:
        return code
    return "en"


def set_language_code(code=None):
    global _LANGUAGE_OVERRIDE
    _LANGUAGE_OVERRIDE = _normalize_language_code(code)
    return language_code()


def language_code():
    return _language_code()


def tr(key):
    lang = _language_code()
    if lang in _MESSAGES and key in _MESSAGES[lang]:
        return _MESSAGES[lang][key]
    return _MESSAGES["en"].get(key, _MESSAGES["ko"].get(key, key))
