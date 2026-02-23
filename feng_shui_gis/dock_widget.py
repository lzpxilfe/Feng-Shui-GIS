# -*- coding: utf-8 -*-
from html import escape

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
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
        self.setStyleSheet(self._dialog_stylesheet())
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        tabs = QTabWidget(self)
        tabs.setDocumentMode(True)
        tabs.addTab(self._browser(self._overview_html()), tr("help_tab_overview"))
        tabs.addTab(self._browser(self._symbols_html()), tr("help_tab_symbols"))
        tabs.addTab(self._browser(self._refs_html()), tr("help_tab_references"))
        layout.addWidget(tabs)

    @staticmethod
    def _browser(html):
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setReadOnly(True)
        browser.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        browser.setUndoRedoEnabled(False)
        browser.setHtml(html)
        return browser

    @staticmethod
    def _dialog_stylesheet():
        return """
            QDialog {
                background-color: #f6f2e8;
                color: #1f2423;
            }
            QTabWidget::pane {
                border: 1px solid #d3c8b3;
                border-radius: 8px;
                background: #fffdf8;
            }
            QTabBar::tab {
                background: #ece4d4;
                border: 1px solid #d3c8b3;
                padding: 7px 12px;
                margin-right: 3px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #fffdf8;
                color: #173736;
                font-weight: 600;
            }
            QTextBrowser {
                border: none;
                background: #fffdf8;
                padding: 10px;
                color: #1f2423;
            }
            QScrollBar:vertical {
                background: #efe8d8;
                width: 12px;
                margin: 2px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #bfae92;
                border-radius: 6px;
                min-height: 26px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a89579;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                width: 0px;
            }
        """

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
            <p><b>클릭 설명</b>: 각 레이어의 피처를 식별(Identify)하면 <code>reason_ko</code> 또는 <code>fs_reason</code> 필드에서
            왜 해당 분류/점수가 나왔는지 상세 근거를 확인할 수 있습니다.</p>
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
        self.resize(680, 820)
        self.setMinimumSize(620, 760)
        self._help_dialog = None
        self.setStyleSheet(self._main_stylesheet())
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hero = QFrame(self)
        hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(14, 12, 14, 12)
        hero_layout.setSpacing(4)
        title = QLabel(tr("panel_title"), hero)
        title.setObjectName("heroTitle")
        subtitle = QLabel(tr("panel_subtitle"), hero)
        subtitle.setObjectName("heroSubtitle")
        subtitle.setWordWrap(True)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        layout.addWidget(hero)

        controls = QFrame(self)
        controls.setObjectName("sectionCard")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(14, 12, 14, 14)
        controls_layout.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
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
        controls_layout.addLayout(form)
        layout.addWidget(controls)

        tabs = QTabWidget(self)
        tabs.setDocumentMode(True)
        tabs.setObjectName("modeTabs")
        tabs.addTab(self._build_landscape_tab(), tr("tab_landscape"))
        tabs.addTab(self._build_analysis_tab(), tr("tab_analysis"))
        layout.addWidget(tabs)

        self.status_label = QLabel(tr("status_idle"), self)
        self.status_label.setObjectName("statusPill")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(38)
        layout.addWidget(self.status_label)

        help_row = QHBoxLayout()
        self.help_button = QPushButton(tr("help_button"), self)
        self.help_button.setObjectName("helpButton")
        self.help_button.clicked.connect(self._open_help_dialog)
        help_row.addWidget(self.help_button)
        help_row.addStretch(1)
        layout.addLayout(help_row)

    def _build_landscape_tab(self):
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        card = QFrame(tab)
        card.setObjectName("tabCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        desc = QLabel(tr("landscape_desc"), card)
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        self.landscape_auto_hydro_checkbox = QCheckBox(tr("auto_hydro_label"), card)
        self.landscape_auto_hydro_checkbox.setChecked(True)
        card_layout.addWidget(self.landscape_auto_hydro_checkbox)

        self.include_terms_checkbox = QCheckBox(tr("include_terms_label"), card)
        self.include_terms_checkbox.setChecked(False)
        card_layout.addWidget(self.include_terms_checkbox)

        self.extract_terms_button = QPushButton(tr("extract_landscape_button"), card)
        self.extract_terms_button.setObjectName("primaryAction")
        self.extract_terms_button.clicked.connect(self._emit_terms_requested)
        card_layout.addWidget(self.extract_terms_button)
        layout.addWidget(card)
        layout.addStretch(1)
        return tab

    def _build_analysis_tab(self):
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        card = QFrame(tab)
        card.setObjectName("tabCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        desc = QLabel(tr("analysis_desc"), card)
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        self.analysis_auto_hydro_checkbox = QCheckBox(
            tr("analysis_auto_hydro_label"), card
        )
        self.analysis_auto_hydro_checkbox.setChecked(True)
        card_layout.addWidget(self.analysis_auto_hydro_checkbox)

        self.run_button = QPushButton(tr("run_button"), card)
        self.run_button.setObjectName("primaryAction")
        self.run_button.clicked.connect(self._emit_run_requested)
        card_layout.addWidget(self.run_button)
        layout.addWidget(card)
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

    @staticmethod
    def _main_stylesheet():
        return """
            QWidget {
                background: #f4efe3;
                color: #1f2423;
                font-size: 12px;
            }
            QLabel {
                background: transparent;
            }
            QFrame#heroCard {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #2d6258,
                    stop: 1 #1d4740
                );
                border: 1px solid #173736;
                border-radius: 12px;
            }
            QLabel#heroTitle {
                background: transparent;
                color: #f7fbf3;
                font-size: 20px;
                font-weight: 700;
            }
            QLabel#heroSubtitle {
                background: transparent;
                color: #d8e8df;
                font-size: 12px;
            }
            QFrame#sectionCard {
                background: #fffdf8;
                border: 1px solid #d6cab3;
                border-radius: 12px;
            }
            QFrame#tabCard {
                background: #fffdf9;
                border: 1px solid #ddd2bf;
                border-radius: 10px;
            }
            QLabel#statusPill {
                background: #edf5f2;
                border: 1px solid #c7ddd6;
                border-radius: 9px;
                padding: 8px 10px;
            }
            QComboBox, QgsMapLayerComboBox, QLineEdit {
                background: #ffffff;
                border: 1px solid #cdbfa7;
                border-radius: 6px;
                padding: 5px 7px;
                min-height: 28px;
            }
            QComboBox:hover, QgsMapLayerComboBox:hover {
                border-color: #bcae96;
            }
            QComboBox:focus, QgsMapLayerComboBox:focus, QLineEdit:focus {
                border: 1px solid #2d6258;
            }
            QCheckBox {
                padding: 2px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid #bcae96;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #2d6258;
                border: 1px solid #1f4a42;
            }
            QTabWidget::pane {
                border: 1px solid #d6cab3;
                border-radius: 8px;
                background: #fffdf8;
            }
            QTabBar::tab {
                background: #ece4d4;
                border: 1px solid #d6cab3;
                padding: 7px 12px;
                margin-right: 3px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #fffdf8;
                color: #173736;
                font-weight: 600;
            }
            QPushButton#primaryAction {
                background: #1f6255;
                color: #f5f9f6;
                border: 1px solid #134c41;
                border-radius: 8px;
                padding: 9px 12px;
                font-weight: 600;
            }
            QPushButton#primaryAction:hover {
                background: #257160;
            }
            QPushButton#primaryAction:pressed {
                background: #1b5549;
            }
            QPushButton#helpButton {
                background: #f4f1e8;
                border: 1px solid #cbbfa9;
                border-radius: 7px;
                padding: 6px 11px;
            }
            QPushButton#helpButton:hover {
                background: #ece4d4;
            }
            QScrollBar:vertical {
                background: #efe8d8;
                width: 12px;
                margin: 2px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #bfae92;
                border-radius: 6px;
                min-height: 26px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a89579;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                width: 0px;
            }
        """
