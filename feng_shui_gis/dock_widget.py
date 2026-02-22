# -*- coding: utf-8 -*-
from html import escape

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox

from .cultural_context import (
    available_cultures,
    available_periods,
    culture_label,
    period_label,
)
from .locale import language_code, tr
from .profile_catalog import (
    available_profiles,
    line_styles,
    profile_label,
    term_label_ko,
)


TERM_MEANINGS_KO = {
    "jusan": "혈 뒤쪽 중심 주봉(배산의 핵심)",
    "jojongsan": "멀리 연결되는 조상산 계열 능선",
    "dunoe": "주산에서 혈로 이어지는 맥의 중간 마디",
    "naecheongnyong": "혈 좌측 가까운 내청룡",
    "oecheongnyong": "혈 좌측 바깥 외청룡",
    "naebaekho": "혈 우측 가까운 내백호",
    "oebaekho": "혈 우측 바깥 외백호",
    "ansan": "혈 전면 가까운 안산",
    "josan": "혈 전면 원경의 조산",
    "naesugu": "혈 전면 가까운 내수구(수로 축)",
    "oesugu": "혈 전면 외곽의 외수구(배수 출구 축)",
    "ipsu": "수맥/수계 유입 축",
    "myeongdang": "혈 전면 완경사·평탄 후보 축",
    "misa": "완만하게 감싸는 미사(곡선형) 축",
}

RIDGE_CLASS_KO = {
    "daegan": "대간",
    "jeongmaek": "정맥",
    "gimaek": "기맥",
    "jimaek": "지맥",
}

HYDRO_CLASS_KO = {
    "main": "주수계",
    "secondary": "중간 수계",
    "branch": "지류",
    "minor": "미소 수로",
}


class FengShuiHelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("help_dialog_title"))
        self.resize(760, 640)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget(self)
        tabs.addTab(self._browser(self._overview_html()), tr("help_tab_overview"))
        tabs.addTab(self._browser(self._symbols_html()), tr("help_tab_symbols"))
        tabs.addTab(self._browser(self._refs_html()), tr("help_tab_references"))
        layout.addWidget(tabs)

    @staticmethod
    def _browser(html):
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setReadOnly(True)
        browser.setHtml(html)
        return browser

    @staticmethod
    def _line_legend_rows():
        rows = []
        for term_id, style in line_styles().items():
            color, width = style
            rows.append(
                (
                    "<tr>"
                    f"<td>{escape(term_label_ko(term_id))}</td>"
                    f"<td>{escape(TERM_MEANINGS_KO.get(term_id, ''))}</td>"
                    f"<td><code>{escape(color)}</code></td>"
                    f"<td>{width:.1f}</td>"
                    "</tr>"
                )
            )
        return "".join(rows)

    @staticmethod
    def _ridge_legend_rows():
        specs = [
            ("daegan", "#000000", 3.8, 0.55),
            ("jeongmaek", "#171717", 3.0, 0.45),
            ("gimaek", "#292929", 2.2, 0.36),
            ("jimaek", "#404040", 1.5, 0.28),
        ]
        rows = []
        for class_id, color, width, opacity in specs:
            rows.append(
                (
                    "<tr>"
                    f"<td>{escape(RIDGE_CLASS_KO[class_id])}</td>"
                    f"<td><code>{escape(color)}</code></td>"
                    f"<td>{width:.1f}</td>"
                    f"<td>{opacity:.2f}</td>"
                    "</tr>"
                )
            )
        return "".join(rows)

    @staticmethod
    def _hydro_legend_rows():
        specs = [
            ("main", "#0b3d91", 2.8),
            ("secondary", "#1456b8", 2.2),
            ("branch", "#2b7bd8", 1.7),
            ("minor", "#63a5ff", 1.2),
        ]
        rows = []
        for class_id, color, width in specs:
            rows.append(
                (
                    "<tr>"
                    f"<td>{escape(HYDRO_CLASS_KO[class_id])}</td>"
                    f"<td><code>{escape(color)}</code></td>"
                    f"<td>{width:.1f}</td>"
                    "</tr>"
                )
            )
        return "".join(rows)

    @staticmethod
    def _overview_html():
        return """
            <h3>기본 워크플로우</h3>
            <p><b>1) 기본 지형 모드</b>: DEM(+선택 수계)에서 능선/수계 네트워크를 먼저 추출합니다.</p>
            <p><b>2) 수계 미입력 시</b>: DEM 기반 자동 수문 추출을 실행합니다.</p>
            <p><b>3) 상세 용어</b>: 필요 시 혈/명당/청룡/백호 등 용어 포인트/구조 연결선을 추가합니다.</p>
            <p><b>4) 고급 분석 모드</b>: 후보지 포인트가 있을 때 점수 분석(<code>fs_score</code>)을 실행합니다.</p>
            <p><b>권장</b>: 경위도 대신 미터 단위 투영 좌표계(UTM/TM) 사용.</p>
        """

    def _symbols_html(self):
        line_rows = self._line_legend_rows()
        ridge_rows = self._ridge_legend_rows()
        hydro_rows = self._hydro_legend_rows()
        return f"""
            <h3>심볼과 의미</h3>
            <p><b>풍수 구조 연결선</b> (방사형이 아닌 구조형 연결)</p>
            <table border="1" cellspacing="0" cellpadding="4">
                <tr><th>용어</th><th>의미</th><th>색</th><th>두께</th></tr>
                {line_rows}
            </table>
            <br>
            <p><b>산맥 계층(산경표식)</b></p>
            <table border="1" cellspacing="0" cellpadding="4">
                <tr><th>계층</th><th>색</th><th>두께</th><th>투명도</th></tr>
                {ridge_rows}
            </table>
            <br>
            <p><b>수계 계층</b></p>
            <table border="1" cellspacing="0" cellpadding="4">
                <tr><th>계층</th><th>색</th><th>두께</th></tr>
                {hydro_rows}
            </table>
        """

    @staticmethod
    def _refs_html():
        return """
            <h3>연구 참고</h3>
            <p>- Han et al. 2021 (GIS 풍수 지표): <a href="https://www.mdpi.com/2071-1050/13/15/8532">link</a></p>
            <p>- Sun et al. 2024 (왕릉 수문/풍수): <a href="https://doi.org/10.1038/s40494-024-01301-1">link</a></p>
            <p>- IJGI 2025 APM review: <a href="https://www.mdpi.com/2220-9964/14/4/133">link</a></p>
            <p><small>자동 결과는 연구용 후보이며 최종 판정이 아닙니다.</small></p>
        """


class FengShuiDockWidget(QWidget):
    run_requested = pyqtSignal(object, object, object, str, str, str, str, bool)
    terms_requested = pyqtSignal(object, object, str, str, str, bool, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle(tr("panel_title"))
        self.resize(620, 760)
        self._help_dialog = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel(f"<h2>{escape(tr('panel_title'))}</h2><p>{escape(tr('panel_subtitle'))}</p>")
        title.setWordWrap(True)
        layout.addWidget(title)

        form = QFormLayout()
        self.sites_combo = QgsMapLayerComboBox(self)
        self.sites_combo.setFilters(QgsMapLayerProxyModel.PointLayer)
        form.addRow(tr("sites_label"), self.sites_combo)

        self.dem_combo = QgsMapLayerComboBox(self)
        self.dem_combo.setFilters(QgsMapLayerProxyModel.RasterLayer)
        form.addRow(tr("dem_label"), self.dem_combo)

        self.water_combo = QgsMapLayerComboBox(self)
        self.water_combo.setFilters(
            QgsMapLayerProxyModel.LineLayer | QgsMapLayerProxyModel.PolygonLayer
        )
        self.water_combo.setAllowEmptyLayer(True)
        self.water_combo.setCurrentIndex(-1)
        form.addRow(tr("water_label"), self.water_combo)

        self.hemisphere_combo = QComboBox(self)
        self.hemisphere_combo.addItem(tr("hemisphere_north"), "north")
        self.hemisphere_combo.addItem(tr("hemisphere_south"), "south")
        form.addRow(tr("hemisphere_label"), self.hemisphere_combo)

        lang = language_code()
        self.profile_combo = QComboBox(self)
        profile_keys = list(available_profiles()) or ["general"]
        for profile_key in profile_keys:
            self.profile_combo.addItem(profile_label(profile_key, lang), profile_key)
        form.addRow(tr("model_label"), self.profile_combo)

        self.culture_combo = QComboBox(self)
        culture_keys = list(available_cultures()) or ["east_asia"]
        for culture_key in culture_keys:
            self.culture_combo.addItem(culture_label(culture_key, lang), culture_key)
        form.addRow(tr("culture_label"), self.culture_combo)

        self.period_combo = QComboBox(self)
        period_keys = list(available_periods()) or ["early_modern"]
        for period_key in period_keys:
            self.period_combo.addItem(period_label(period_key, lang), period_key)
        if "early_modern" in period_keys:
            self.period_combo.setCurrentIndex(period_keys.index("early_modern"))
        form.addRow(tr("period_label"), self.period_combo)
        layout.addLayout(form)

        tabs = QTabWidget(self)
        tabs.addTab(self._build_landscape_tab(), tr("tab_landscape"))
        tabs.addTab(self._build_analysis_tab(), tr("tab_analysis"))
        layout.addWidget(tabs)

        self.status_label = QLabel(tr("status_idle"), self)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        help_row = QHBoxLayout()
        self.help_button = QPushButton(tr("help_button"), self)
        self.help_button.clicked.connect(self._open_help_dialog)
        help_row.addWidget(self.help_button)
        help_row.addStretch(1)
        layout.addLayout(help_row)

    def _build_landscape_tab(self):
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        desc = QLabel(tr("landscape_desc"), tab)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.landscape_auto_hydro_checkbox = QCheckBox(tr("auto_hydro_label"), tab)
        self.landscape_auto_hydro_checkbox.setChecked(True)
        layout.addWidget(self.landscape_auto_hydro_checkbox)

        self.include_terms_checkbox = QCheckBox(tr("include_terms_label"), tab)
        self.include_terms_checkbox.setChecked(False)
        layout.addWidget(self.include_terms_checkbox)

        self.extract_terms_button = QPushButton(tr("extract_landscape_button"), tab)
        self.extract_terms_button.clicked.connect(self._emit_terms_requested)
        layout.addWidget(self.extract_terms_button)
        layout.addStretch(1)
        return tab

    def _build_analysis_tab(self):
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        desc = QLabel(tr("analysis_desc"), tab)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.analysis_auto_hydro_checkbox = QCheckBox(
            tr("analysis_auto_hydro_label"), tab
        )
        self.analysis_auto_hydro_checkbox.setChecked(True)
        layout.addWidget(self.analysis_auto_hydro_checkbox)

        self.run_button = QPushButton(tr("run_button"), tab)
        self.run_button.clicked.connect(self._emit_run_requested)
        layout.addWidget(self.run_button)
        layout.addStretch(1)
        return tab

    def _open_help_dialog(self):
        if self._help_dialog is None:
            self._help_dialog = FengShuiHelpDialog(self)
        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()

    def set_status(self, text):
        self.status_label.setText(text)

    def _emit_run_requested(self):
        self.run_requested.emit(
            self.sites_combo.currentLayer(),
            self.dem_combo.currentLayer(),
            self.water_combo.currentLayer(),
            self.hemisphere_combo.currentData(),
            self.profile_combo.currentData(),
            self.culture_combo.currentData(),
            self.period_combo.currentData(),
            self.analysis_auto_hydro_checkbox.isChecked(),
        )

    def _emit_terms_requested(self):
        self.terms_requested.emit(
            self.dem_combo.currentLayer(),
            self.water_combo.currentLayer(),
            self.hemisphere_combo.currentData(),
            self.culture_combo.currentData(),
            self.period_combo.currentData(),
            self.landscape_auto_hydro_checkbox.isChecked(),
            self.include_terms_checkbox.isChecked(),
        )
