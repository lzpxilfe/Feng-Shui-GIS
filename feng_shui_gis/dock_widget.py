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
    QSpinBox,
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
    context_evidence_html,
    context_evidence_records,
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
    "jusan": "주산: 혈 뒤편의 중심 산",
    "jojongsan": "조종산: 계통의 상위 산줄기",
    "dunoe": "두뇌: 주산에서 이어지는 마디",
    "naecheongnyong": "내청룡: 좌측의 가까운 지지 능선",
    "oecheongnyong": "외청룡: 좌측의 바깥 지지 능선",
    "naebaekho": "내백호: 우측의 가까운 지지 능선",
    "oebaekho": "외백호: 우측의 바깥 지지 능선",
    "ansan": "안산: 전면의 가까운 받침 산",
    "josan": "조산: 전면의 원거리 받침 산",
    "naesugu": "내수구: 전면의 가까운 수구",
    "oesugu": "외수구: 전면의 원거리 수구",
    "ipsu": "입수: 유입 수로 지점",
    "myeongdang": "명당: 중심의 완만한 평탄부",
    "misa": "미사: 전면의 완경사 지대",
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
            ("main", "#0b3d91", 1.6),
            ("secondary", "#1456b8", 1.2),
            ("branch", "#2b7bd8", 0.9),
            ("minor", "#63a5ff", 0.7),
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
            <p><b>1) 기본 지형 모드</b>: DEM(+선택 수계)에서 능선/수계 흐름을 먼저 추출합니다.</p>
            <p><b>2) 수계가 없을 때</b>: DEM 기반 자동 수문 추출을 실행합니다.</p>
            <p><b>3) 상세 용어</b>: 필요할 때만 혈/명당/청룡/백호 등 용어 포인트와 구조 연결을 생성합니다.</p>
            <p><b>4) 고급 분석 모드</b>: 후보지 점 레이어가 있을 때만 입지 점수(<code>fs_score</code>)를 계산합니다.</p>
            <p><b>클릭 설명</b>: 레이어 피처를 식별(Identify)하거나 선택하면 <code>reason_ko</code> 또는
            <code>fs_reason</code> 필드에서 해당 결과의 근거(점수, 임계치, 거리/방위 등)를 확인할 수 있습니다.</p>
            <p><b>권장</b>: 거리 해석이 필요한 분석이므로 투영좌표계(UTM/TM, meter 단위)를 권장합니다.</p>
        """

    def _symbols_html(self):
        line_rows = self._line_legend_rows()
        ridge_rows = self._ridge_legend_rows()
        hydro_rows = self._hydro_legend_rows()
        return f"""
            <h3>결과 심볼 안내</h3>
            <p><b>풍수 구조 연결선</b> (중심 방사형이 아닌 구조-구조 연결)</p>
            <table border="1" cellspacing="0" cellpadding="4">
                <tr><th>용어</th><th>의미</th><th>색</th><th>선폭</th></tr>
                {line_rows}
            </table>
            <br>
            <p><b>능선 계층(산경표식)</b></p>
            <table border="1" cellspacing="0" cellpadding="4">
                <tr><th>계층</th><th>색</th><th>선폭</th><th>투명도</th></tr>
                {ridge_rows}
            </table>
            <br>
            <p><b>수계 계층</b></p>
            <table border="1" cellspacing="0" cellpadding="4">
                <tr><th>계층</th><th>색</th><th>선폭</th></tr>
                {hydro_rows}
            </table>
        """

    @staticmethod
    def _refs_html():
        return """
            <h3>연구 참고 (검증된 DOI, 2026-02-23 재점검)</h3>
            <p><b>직접 근거: 풍수 + 공간/GIS 정량</b></p>
            <p>- Um (2009), IJGIS:
               <a href="https://doi.org/10.1080/13658810802055954">10.1080/13658810802055954</a></p>
            <p>- Tung Fung &amp; Marafa (2002), IGARSS:
               <a href="https://doi.org/10.1109/IGARSS.2002.1027144">10.1109/IGARSS.2002.1027144</a></p>
            <p>- Whang &amp; Lee (2006), Landscape and Ecological Engineering:
               <a href="https://doi.org/10.1007/s11355-006-0014-8">10.1007/s11355-006-0014-8</a></p>
            <p>- Kim (2016), Journal of Koreanology:
               <a href="https://doi.org/10.15299/jk.2016.8.60.203">10.15299/jk.2016.8.60.203</a></p>
            <p><b>맥락 근거: 지역별 해석 전통</b></p>
            <p>- Ryukyu/Okinawa 사례:
               <a href="https://doi.org/10.1163/156853508X276824">10.1163/156853508X276824</a>,
               <a href="https://doi.org/10.1163/156853511X577475">10.1163/156853511X577475</a>,
               <a href="https://doi.org/10.1016/j.ufug.2007.10.001">10.1016/j.ufug.2007.10.001</a></p>
            <p>- Choson geomancy/architecture:
               <a href="https://doi.org/10.1515/9781438468716-011">10.1515/9781438468716-011</a>,
               <a href="https://doi.org/10.1515/9781438468716-009">10.1515/9781438468716-009</a></p>
            <p><small>주의: 국가/시대 파라미터는 위 문헌의 직접 근거 + 연구 가설 초기값 조합입니다.
               현장 유적 데이터로 재보정이 필요합니다.</small></p>
        """


class ContextEvidenceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("컨텍스트 근거")
        self.resize(860, 620)
        self.setStyleSheet(FengShuiHelpDialog._dialog_stylesheet())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        self.browser = QTextBrowser(self)
        self.browser.setOpenExternalLinks(True)
        self.browser.setReadOnly(True)
        self.browser.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.browser)

    def set_html(self, html):
        self.browser.setHtml(html)


class FengShuiDockWidget(QWidget):
    run_requested = pyqtSignal(object, object, object, str, str, str, str, bool)
    terms_requested = pyqtSignal(object, object, str, str, str, bool, bool)
    calibration_requested = pyqtSignal(
        object,
        object,
        object,
        str,
        str,
        str,
        str,
        int,
        int,
        bool,
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle(tr("panel_title"))
        self.resize(680, 820)
        self.setMinimumSize(620, 760)
        self._help_dialog = None
        self._context_evidence_dialog = None
        self._context_records = []
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

        self.context_param_combo = QComboBox(self)
        form.addRow("근거 파라미터", self.context_param_combo)

        evidence_row = QHBoxLayout()
        self.context_evidence_button = QPushButton("컨텍스트 근거 보기", self)
        self.context_evidence_button.setObjectName("helpButton")
        self.context_evidence_button.clicked.connect(self._open_context_evidence_dialog)
        evidence_row.addWidget(self.context_evidence_button)
        evidence_row.addStretch(1)

        self.context_evidence_hint = QLabel("", self)
        self.context_evidence_hint.setObjectName("contextHint")
        self.context_evidence_hint.setWordWrap(True)

        self.context_param_hint = QLabel("", self)
        self.context_param_hint.setObjectName("contextParamHint")
        self.context_param_hint.setWordWrap(True)

        controls_layout.addLayout(form)
        controls_layout.addLayout(evidence_row)
        controls_layout.addWidget(self.context_evidence_hint)
        controls_layout.addWidget(self.context_param_hint)
        layout.addWidget(controls)

        self.culture_combo.currentIndexChanged.connect(self._update_context_evidence_hint)
        self.period_combo.currentIndexChanged.connect(self._update_context_evidence_hint)
        self.hemisphere_combo.currentIndexChanged.connect(self._update_context_evidence_hint)
        self.context_param_combo.currentIndexChanged.connect(self._update_selected_param_evidence_hint)
        self._update_context_evidence_hint()

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

        ratio_row = QHBoxLayout()
        ratio_label = QLabel("음성 샘플 배수", card)
        self.negative_ratio_combo = QComboBox(card)
        self.negative_ratio_combo.addItem("1x", 1)
        self.negative_ratio_combo.addItem("2x", 2)
        self.negative_ratio_combo.addItem("3x (권장)", 3)
        self.negative_ratio_combo.addItem("4x", 4)
        self.negative_ratio_combo.setCurrentIndex(2)
        ratio_row.addWidget(ratio_label)
        ratio_row.addWidget(self.negative_ratio_combo, 1)
        card_layout.addLayout(ratio_row)

        seed_row = QHBoxLayout()
        seed_label = QLabel("랜덤 시드", card)
        self.calibration_seed_spin = QSpinBox(card)
        self.calibration_seed_spin.setRange(1, 999999)
        self.calibration_seed_spin.setValue(42)
        seed_row.addWidget(seed_label)
        seed_row.addWidget(self.calibration_seed_spin, 1)
        card_layout.addLayout(seed_row)

        self.run_button = QPushButton(tr("run_button"), card)
        self.run_button.setObjectName("primaryAction")
        self.run_button.clicked.connect(self._emit_run_requested)
        card_layout.addWidget(self.run_button)

        self.calibration_button = QPushButton(
            "한국 SHP 캘리브레이션 (ROC/AUC 리포트)",
            card,
        )
        self.calibration_button.setObjectName("helpButton")
        self.calibration_button.clicked.connect(self._emit_calibration_requested)
        card_layout.addWidget(self.calibration_button)
        layout.addWidget(card)
        layout.addStretch(1)
        return tab

    def _open_help_dialog(self):
        if self._help_dialog is None:
            self._help_dialog = FengShuiHelpDialog(self)
        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()

    def _open_context_evidence_dialog(self):
        html = context_evidence_html(
            culture_key=self.culture_combo.currentData(),
            period_key=self.period_combo.currentData(),
            hemisphere=self.hemisphere_combo.currentData(),
        )
        if self._context_evidence_dialog is None:
            self._context_evidence_dialog = ContextEvidenceDialog(self)
        self._context_evidence_dialog.set_html(html)
        self._context_evidence_dialog.show()
        self._context_evidence_dialog.raise_()
        self._context_evidence_dialog.activateWindow()

    def _update_context_evidence_hint(self, *_args):
        records = context_evidence_records(
            culture_key=self.culture_combo.currentData(),
            period_key=self.period_combo.currentData(),
            hemisphere=self.hemisphere_combo.currentData(),
        )
        self._context_records = records

        selected_key = self.context_param_combo.currentData()
        self.context_param_combo.blockSignals(True)
        self.context_param_combo.clear()
        for index, item in enumerate(records):
            group = item.get("group", "-")
            name = item.get("name", "-")
            self.context_param_combo.addItem(f"{group}.{name}", index)
        if records:
            if isinstance(selected_key, int) and 0 <= selected_key < len(records):
                self.context_param_combo.setCurrentIndex(selected_key)
            else:
                self.context_param_combo.setCurrentIndex(0)
        self.context_param_combo.blockSignals(False)

        source_list = []
        for item in records:
            for source in item.get("source_doi", []):
                if source not in source_list:
                    source_list.append(source)
            if len(source_list) >= 2:
                break
        hint = (
            f"현재 프로필 근거: {self.culture_combo.currentText()} / "
            f"{self.period_combo.currentText()} (상세는 '컨텍스트 근거 보기')."
        )
        if source_list:
            hint += f" 대표 DOI: {source_list[0]}"
            if len(source_list) > 1:
                hint += f", {source_list[1]}"
        self.context_evidence_hint.setText(hint)
        self._update_selected_param_evidence_hint()

    def _update_selected_param_evidence_hint(self, *_args):
        if not self._context_records:
            self.context_param_hint.setText("선택 가능한 파라미터 근거가 없습니다.")
            return

        index = self.context_param_combo.currentIndex()
        if index < 0 or index >= len(self._context_records):
            index = 0
        item = self._context_records[index]
        value = item.get("value")
        if isinstance(value, float):
            value_text = f"{value:.4f}".rstrip("0").rstrip(".")
        else:
            value_text = str(value)
        level = item.get("evidence_level", "U")
        dois = item.get("source_doi", [])
        doi_text = ", ".join(dois) if dois else "DOI 없음"
        note = item.get("note") or "설명 없음"
        self.context_param_hint.setText(
            f"[{item.get('group', '-')}.{item.get('name', '-')}] "
            f"값={value_text} | 근거수준={level} | DOI={doi_text} | 메모={note}"
        )

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

    def _emit_calibration_requested(self):
        self.calibration_requested.emit(
            self.sites_combo.currentLayer(),
            self.dem_combo.currentLayer(),
            self.water_combo.currentLayer(),
            self.hemisphere_combo.currentData(),
            self.profile_combo.currentData(),
            self.culture_combo.currentData(),
            self.period_combo.currentData(),
            int(self.negative_ratio_combo.currentData()),
            int(self.calibration_seed_spin.value()),
            self.analysis_auto_hydro_checkbox.isChecked(),
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
            QLabel#contextHint {
                color: #38534c;
                font-size: 11px;
                padding: 2px 0px;
            }
            QLabel#contextParamHint {
                color: #2c413c;
                font-size: 11px;
                padding: 2px 0px 4px 0px;
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

