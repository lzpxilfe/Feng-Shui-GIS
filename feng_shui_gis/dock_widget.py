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
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextBrowser,
    QToolButton,
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
    neutral_context_key,
    period_label,
)
from .locale import language_code, tr
from .mountain_options import mountain_options
from .profile_catalog import (
    analysis_rules,
    available_profiles,
    line_styles,
    profile_label,
    term_label_ko,
)
from .reference_catalog import reference_display_text, references_help_html
from .ui_catalog import (
    ui_help_html,
    ui_hydro_legend,
    ui_metric_help_items,
    ui_ridge_legend,
    ui_term_meanings,
    ui_text,
)


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
        tabs.addTab(
            self._browser(self._quick_terms_html()),
            ui_text("help_tab_quick_terms", default="Number Guide"),
        )
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
        meanings = ui_term_meanings("ko")
        rows = []
        for term_id, style in line_styles().items():
            color, width = style
            rows.append(
                (
                    "<tr>"
                    f"<td>{escape(term_label_ko(term_id))}</td>"
                    f"<td>{escape(str(meanings.get(term_id, '')))}</td>"
                    f"<td><code>{escape(color)}</code></td>"
                    f"<td>{width:.1f}</td>"
                    "</tr>"
                )
            )
        return "".join(rows)

    @staticmethod
    def _ridge_legend_rows():
        rows = []
        for item in ui_ridge_legend("ko"):
            rows.append(
                (
                    "<tr>"
                    f"<td>{escape(item.get('label', ''))}</td>"
                    f"<td><code>{escape(item.get('color', ''))}</code></td>"
                    f"<td>{float(item.get('width', 0.0)):.1f}</td>"
                    f"<td>{float(item.get('opacity', 0.0)):.2f}</td>"
                    "</tr>"
                )
            )
        return "".join(rows)

    @staticmethod
    def _hydro_legend_rows():
        rows = []
        for item in ui_hydro_legend("ko"):
            rows.append(
                (
                    "<tr>"
                    f"<td>{escape(item.get('label', ''))}</td>"
                    f"<td><code>{escape(item.get('color', ''))}</code></td>"
                    f"<td>{float(item.get('width', 0.0)):.1f}</td>"
                    "</tr>"
                )
            )
        return "".join(rows)

    @staticmethod
    def _overview_html():
        return ui_help_html("overview")

    @staticmethod
    def _quick_terms_html():
        return ui_help_html("quick_terms")

    def _symbols_html(self):
        line_rows = self._line_legend_rows()
        ridge_rows = self._ridge_legend_rows()
        hydro_rows = self._hydro_legend_rows()
        return ui_help_html(
            "symbols",
            line_rows=line_rows,
            ridge_rows=ridge_rows,
            hydro_rows=hydro_rows,
        )

    @staticmethod
    def _refs_html():
        return references_help_html()


class ContextEvidenceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(ui_text("context_evidence_title", default="Context Evidence"))
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
    terms_requested = pyqtSignal(object, object, str, str, str, str, bool, bool)
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
    GOAL_PROFILE_MAP = {
        "tomb": "tomb",
        "house": "house",
        "general": "general",
    }
    PROFILE_GOAL_MAP = {
        "tomb": "tomb",
        "house": "house",
        "general": "general",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle(tr("panel_title"))
        self.resize(640, 720)
        self.setMinimumSize(540, 560)
        self._help_dialog = None
        self._context_evidence_dialog = None
        self._context_records = []
        self._syncing_goal_controls = False
        self.setStyleSheet(self._main_stylesheet())
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setObjectName("panelScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        root_layout.addWidget(scroll)

        content = QWidget(scroll)
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
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

        self.purpose_combo = QComboBox(self)
        self.purpose_combo.addItem(
            ui_text("goal_tomb_label", default="음택(무덤 자리)"),
            "tomb",
        )
        self.purpose_combo.addItem(
            ui_text("goal_house_label", default="양택(집터/거주지)"),
            "house",
        )
        self.purpose_combo.addItem(
            ui_text("goal_general_label", default="일반 지형 읽기"),
            "general",
        )
        self.purpose_combo.addItem(
            ui_text("goal_custom_label", default="직접 설정"),
            "custom",
        )
        form.addRow(ui_text("goal_label", default="탐색 목적"), self.purpose_combo)

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

        self.label_language_combo = QComboBox(self)
        self.label_language_combo.addItem(ui_text("language_ko", default="Korean"), "ko")
        self.label_language_combo.addItem(ui_text("language_en", default="English"), "en")
        self.label_language_combo.setCurrentIndex(0)
        form.addRow(ui_text("label_language", default="Label Language"), self.label_language_combo)

        self.web_mountain_checkbox = QCheckBox(
            ui_text(
                "web_mountain_toggle_label",
                default="Auto-attach nearby mountain names from web (OSM)",
            ),
            self,
        )
        mountain_cfg = mountain_options()
        self.web_mountain_checkbox.setChecked(bool(mountain_cfg["enabled_default"]))
        self.web_mountain_radius_spin = QSpinBox(self)
        self.web_mountain_radius_spin.setRange(
            int(mountain_cfg["radius_min_m"]),
            int(mountain_cfg["radius_max_m"]),
        )
        self.web_mountain_radius_spin.setSingleStep(max(1, int(mountain_cfg["radius_step_m"])))
        self.web_mountain_radius_spin.setValue(int(mountain_cfg["radius_default_m"]))
        self.web_mountain_radius_spin.setSuffix(" m")
        self.web_mountain_limit_spin = QSpinBox(self)
        self.web_mountain_limit_spin.setRange(
            int(mountain_cfg["max_features_min"]),
            int(mountain_cfg["max_features_max"]),
        )
        self.web_mountain_limit_spin.setSingleStep(
            max(1, int(mountain_cfg["max_features_step"]))
        )
        self.web_mountain_limit_spin.setValue(int(mountain_cfg["max_features_default"]))
        self.web_mountain_lang_combo = QComboBox(self)
        self.web_mountain_lang_combo.addItem(
            ui_text("web_mountain_lang_local", default="Local name"),
            "local",
        )
        self.web_mountain_lang_combo.addItem(
            ui_text("web_mountain_lang_ko", default="Korean preferred"),
            "ko",
        )
        self.web_mountain_lang_combo.addItem(
            ui_text("web_mountain_lang_en", default="English preferred"),
            "en",
        )
        default_lang = str(mountain_cfg.get("language_default", "local")).lower()
        lang_index = self.web_mountain_lang_combo.findData(
            default_lang if default_lang in ("local", "ko", "en") else "local"
        )
        self.web_mountain_lang_combo.setCurrentIndex(max(0, lang_index))
        form.addRow(
            ui_text("web_mountain_option_label", default="Mountain naming"),
            self.web_mountain_checkbox,
        )
        form.addRow(
            ui_text("web_mountain_lang_label", default="Mountain name language"),
            self.web_mountain_lang_combo,
        )
        form.addRow(
            ui_text("web_mountain_radius_label", default="Search radius"),
            self.web_mountain_radius_spin,
        )
        form.addRow(
            ui_text("web_mountain_limit_label", default="Max features"),
            self.web_mountain_limit_spin,
        )

        controls_layout.addLayout(form)

        self.goal_hint_label = QLabel("", self)
        self.goal_hint_label.setObjectName("goalHint")
        self.goal_hint_label.setWordWrap(True)
        self.goal_hint_label.setTextFormat(Qt.RichText)
        controls_layout.addWidget(self.goal_hint_label)

        self.advanced_options_button = QToolButton(self)
        self.advanced_options_button.setObjectName("advancedToggle")
        self.advanced_options_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.advanced_options_button.setCheckable(True)
        self.advanced_options_button.setChecked(False)
        self.advanced_options_button.setArrowType(Qt.RightArrow)
        self.advanced_options_button.setText(
            ui_text("advanced_options_button", default="Advanced Options")
        )
        controls_layout.addWidget(self.advanced_options_button)

        self.advanced_options_panel = QFrame(self)
        self.advanced_options_panel.setObjectName("advancedPanel")
        advanced_layout = QVBoxLayout(self.advanced_options_panel)
        advanced_layout.setContentsMargins(10, 8, 10, 8)
        advanced_layout.setSpacing(8)

        advanced_form = QFormLayout()
        advanced_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        advanced_form.setFormAlignment(Qt.AlignTop)
        advanced_form.setHorizontalSpacing(16)
        advanced_form.setVerticalSpacing(8)

        lang = language_code()
        self.profile_combo = QComboBox(self)
        profile_keys = list(available_profiles()) or ["general"]
        for profile_key in profile_keys:
            self.profile_combo.addItem(profile_label(profile_key, lang), profile_key)
        advanced_form.addRow(tr("model_label"), self.profile_combo)

        self.advanced_context_checkbox = QCheckBox(
            ui_text(
                "advanced_context_toggle_label",
                default="Enable advanced context (country/period)",
            ),
            self,
        )
        self.advanced_context_checkbox.setChecked(False)
        advanced_form.addRow(
            ui_text("context_mode_label", default="Context Mode"),
            self.advanced_context_checkbox,
        )

        self.culture_combo = QComboBox(self)
        culture_keys = list(available_cultures()) or ["east_asia"]
        for culture_key in culture_keys:
            self.culture_combo.addItem(culture_label(culture_key, lang), culture_key)
        advanced_form.addRow(tr("culture_label"), self.culture_combo)

        self.period_combo = QComboBox(self)
        period_keys = list(available_periods()) or ["early_modern"]
        for period_key in period_keys:
            self.period_combo.addItem(period_label(period_key, lang), period_key)
        if "early_modern" in period_keys:
            self.period_combo.setCurrentIndex(period_keys.index("early_modern"))
        advanced_form.addRow(tr("period_label"), self.period_combo)

        self.context_param_combo = QComboBox(self)
        advanced_form.addRow(
            ui_text("context_param_label", default="Evidence Parameter"),
            self.context_param_combo,
        )
        advanced_layout.addLayout(advanced_form)

        evidence_row = QHBoxLayout()
        self.context_evidence_button = QPushButton(
            ui_text("context_evidence_button", default="View Context Evidence"),
            self,
        )
        self.context_evidence_button.setObjectName("helpButton")
        self.context_evidence_button.clicked.connect(self._open_context_evidence_dialog)
        evidence_row.addWidget(self.context_evidence_button)
        evidence_row.addStretch(1)
        advanced_layout.addLayout(evidence_row)

        self.context_evidence_hint = QLabel("", self)
        self.context_evidence_hint.setObjectName("contextHint")
        self.context_evidence_hint.setWordWrap(True)
        advanced_layout.addWidget(self.context_evidence_hint)

        self.context_param_hint = QLabel("", self)
        self.context_param_hint.setObjectName("contextParamHint")
        self.context_param_hint.setWordWrap(True)
        advanced_layout.addWidget(self.context_param_hint)

        controls_layout.addWidget(self.advanced_options_panel)
        layout.addWidget(controls)

        self.culture_combo.currentIndexChanged.connect(self._update_context_evidence_hint)
        self.period_combo.currentIndexChanged.connect(self._update_context_evidence_hint)
        self.hemisphere_combo.currentIndexChanged.connect(self._update_context_evidence_hint)
        self.context_param_combo.currentIndexChanged.connect(self._update_selected_param_evidence_hint)
        self.purpose_combo.currentIndexChanged.connect(self._apply_usage_goal_presets)
        self.advanced_context_checkbox.toggled.connect(self._toggle_advanced_context_controls)
        self.advanced_options_button.toggled.connect(self._toggle_advanced_options_panel)
        self.advanced_options_button.toggled.connect(self._refresh_progress_guide)
        self.web_mountain_checkbox.toggled.connect(self._toggle_web_mountain_controls)
        self.web_mountain_checkbox.toggled.connect(self._refresh_progress_guide)
        self.web_mountain_radius_spin.valueChanged.connect(self._refresh_progress_guide)
        self.web_mountain_limit_spin.valueChanged.connect(self._refresh_progress_guide)
        self.web_mountain_lang_combo.currentIndexChanged.connect(self._refresh_progress_guide)
        self._update_context_evidence_hint()

        self.mode_tabs = QTabWidget(self)
        self.mode_tabs.setDocumentMode(True)
        self.mode_tabs.setObjectName("modeTabs")
        self.mode_tabs.addTab(self._build_landscape_tab(), tr("tab_landscape"))
        self.mode_tabs.addTab(self._build_analysis_tab(), tr("tab_analysis"))
        layout.addWidget(self.mode_tabs)

        layout.addWidget(self._build_workflow_guide_card())

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

        self.sites_combo.layerChanged.connect(self._refresh_progress_guide)
        self.dem_combo.layerChanged.connect(self._refresh_progress_guide)
        self.dem_combo.layerChanged.connect(self._update_dem_diagnostics_hint)
        self.water_combo.layerChanged.connect(self._refresh_progress_guide)
        self.mode_tabs.currentChanged.connect(self._refresh_progress_guide)
        self.landscape_auto_hydro_checkbox.toggled.connect(self._refresh_progress_guide)
        self.include_terms_checkbox.toggled.connect(self._refresh_progress_guide)
        self.analysis_auto_hydro_checkbox.toggled.connect(self._refresh_progress_guide)
        self.purpose_combo.currentIndexChanged.connect(self._refresh_progress_guide)
        self.profile_combo.currentIndexChanged.connect(self._refresh_progress_guide)
        self.profile_combo.currentIndexChanged.connect(self._sync_usage_goal_from_profile)
        self.culture_combo.currentIndexChanged.connect(self._refresh_progress_guide)
        self.period_combo.currentIndexChanged.connect(self._refresh_progress_guide)
        self.hemisphere_combo.currentIndexChanged.connect(self._refresh_progress_guide)
        self.label_language_combo.currentIndexChanged.connect(self._refresh_progress_guide)
        self.advanced_context_checkbox.toggled.connect(self._refresh_progress_guide)
        self.label_language_combo.currentIndexChanged.connect(self._update_quick_number_widget)

        self._toggle_advanced_options_panel(False)
        self._toggle_advanced_context_controls()
        self._toggle_web_mountain_controls()
        default_goal_index = max(0, self.purpose_combo.findData("tomb"))
        self.purpose_combo.setCurrentIndex(default_goal_index)
        self._apply_usage_goal_presets()
        self._update_metric_help_hint()
        self._update_quick_number_widget()
        self._update_dem_diagnostics_hint()
        self._update_evidence_summary_widget()
        self._refresh_progress_guide()

    def _build_workflow_guide_card(self):
        card = QFrame(self)
        card.setObjectName("guideCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 12)
        card_layout.setSpacing(6)

        title = QLabel(ui_text("guide_title", default="Progress Guide"), card)
        title.setObjectName("guideTitle")
        card_layout.addWidget(title)

        self.progress_summary_label = QLabel("", card)
        self.progress_summary_label.setObjectName("guideSummary")
        self.progress_summary_label.setWordWrap(True)
        card_layout.addWidget(self.progress_summary_label)

        self.guide_intro_widget = QLabel("", card)
        self.guide_intro_widget.setObjectName("guideWidget")
        self.guide_intro_widget.setWordWrap(True)
        self.guide_intro_widget.setTextFormat(Qt.RichText)
        card_layout.addWidget(self.guide_intro_widget)

        self.guide_steps_widget = QLabel("", card)
        self.guide_steps_widget.setObjectName("guideWidget")
        self.guide_steps_widget.setWordWrap(True)
        self.guide_steps_widget.setTextFormat(Qt.RichText)
        card_layout.addWidget(self.guide_steps_widget)

        self.workflow_progress = QProgressBar(card)
        self.workflow_progress.setObjectName("workflowProgress")
        self.workflow_progress.setRange(0, 100)
        self.workflow_progress.setValue(0)
        self.workflow_progress.setFormat(
            ui_text("workflow_progress_format", default="%p% ready")
        )
        card_layout.addWidget(self.workflow_progress)

        self.next_step_label = QLabel("", card)
        self.next_step_label.setObjectName("guideNext")
        self.next_step_label.setWordWrap(True)
        card_layout.addWidget(self.next_step_label)

        self.checklist_label = QLabel("", card)
        self.checklist_label.setObjectName("guideChecklist")
        self.checklist_label.setWordWrap(True)
        self.checklist_label.setTextFormat(Qt.RichText)
        card_layout.addWidget(self.checklist_label)

        metric_row = QHBoxLayout()
        metric_label = QLabel(ui_text("guide_metric_label", default="Metric Help"), card)
        self.metric_help_combo = QComboBox(card)
        for label, description in ui_metric_help_items():
            self.metric_help_combo.addItem(label, description)
        self.metric_help_combo.currentIndexChanged.connect(self._update_metric_help_hint)
        metric_row.addWidget(metric_label)
        metric_row.addWidget(self.metric_help_combo, 1)
        card_layout.addLayout(metric_row)

        self.metric_help_hint = QLabel("", card)
        self.metric_help_hint.setObjectName("metricHint")
        self.metric_help_hint.setWordWrap(True)
        card_layout.addWidget(self.metric_help_hint)

        self.quick_number_widget = QLabel("", card)
        self.quick_number_widget.setObjectName("guideWidget")
        self.quick_number_widget.setWordWrap(True)
        self.quick_number_widget.setTextFormat(Qt.RichText)
        card_layout.addWidget(self.quick_number_widget)

        self.dem_diag_widget = QLabel("", card)
        self.dem_diag_widget.setObjectName("guideWidget")
        self.dem_diag_widget.setWordWrap(True)
        self.dem_diag_widget.setTextFormat(Qt.RichText)
        card_layout.addWidget(self.dem_diag_widget)

        self.evidence_widget = QLabel("", card)
        self.evidence_widget.setObjectName("guideWidget")
        self.evidence_widget.setWordWrap(True)
        self.evidence_widget.setTextFormat(Qt.RichText)
        card_layout.addWidget(self.evidence_widget)

        self.workflow_status_label = QLabel("", card)
        self.workflow_status_label.setObjectName("guideStatus")
        self.workflow_status_label.setWordWrap(True)
        card_layout.addWidget(self.workflow_status_label)
        return card

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
        calibration_rules = analysis_rules().get("calibration", {})

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
        ratio_label = QLabel(ui_text("negative_ratio_label", default="Negative Ratio"), card)
        self.negative_ratio_combo = QComboBox(card)
        ratio_options = calibration_rules.get("negative_ratio_options", [1, 2, 3, 4])
        clean_options = []
        for value in ratio_options:
            try:
                clean = int(value)
            except (TypeError, ValueError):
                continue
            if clean > 0 and clean not in clean_options:
                clean_options.append(clean)
        if not clean_options:
            clean_options = [1, 2, 3, 4]
        default_ratio = calibration_rules.get("default_negative_ratio", 3)
        try:
            default_ratio = int(default_ratio)
        except (TypeError, ValueError):
            default_ratio = 3
        for value in clean_options:
            label = f"{value}x"
            if value == default_ratio:
                suffix = ui_text("negative_ratio_recommended_suffix", default="(Recommended)")
                label = f"{value}x {suffix}"
            self.negative_ratio_combo.addItem(label, value)
        if default_ratio in clean_options:
            self.negative_ratio_combo.setCurrentIndex(clean_options.index(default_ratio))
        else:
            self.negative_ratio_combo.setCurrentIndex(0)
        ratio_row.addWidget(ratio_label)
        ratio_row.addWidget(self.negative_ratio_combo, 1)
        card_layout.addLayout(ratio_row)

        seed_row = QHBoxLayout()
        seed_label = QLabel(ui_text("seed_label", default="Random Seed"), card)
        self.calibration_seed_spin = QSpinBox(card)
        seed_min = calibration_rules.get("seed_min", 1)
        seed_max = calibration_rules.get("seed_max", 999999)
        seed_default = calibration_rules.get("seed_default", 42)
        try:
            seed_min = int(seed_min)
        except (TypeError, ValueError):
            seed_min = 1
        try:
            seed_max = int(seed_max)
        except (TypeError, ValueError):
            seed_max = 999999
        if seed_max < seed_min:
            seed_max = seed_min
        try:
            seed_default = int(seed_default)
        except (TypeError, ValueError):
            seed_default = 42
        seed_default = max(seed_min, min(seed_max, seed_default))
        self.calibration_seed_spin.setRange(seed_min, seed_max)
        self.calibration_seed_spin.setValue(seed_default)
        seed_row.addWidget(seed_label)
        seed_row.addWidget(self.calibration_seed_spin, 1)
        card_layout.addLayout(seed_row)

        self.run_button = QPushButton(tr("run_button"), card)
        self.run_button.setObjectName("primaryAction")
        self.run_button.clicked.connect(self._emit_run_requested)
        card_layout.addWidget(self.run_button)

        self.calibration_button = QPushButton(
            ui_text(
                "calibration_button",
                default="Korea SHP Calibration (ROC/AUC Report)",
            ),
            card,
        )
        self.calibration_button.setObjectName("helpButton")
        self.calibration_button.clicked.connect(self._emit_calibration_requested)
        card_layout.addWidget(self.calibration_button)
        layout.addWidget(card)
        layout.addStretch(1)
        return tab

    def _advanced_context_enabled(self):
        if not hasattr(self, "advanced_context_checkbox"):
            return False
        return bool(self.advanced_context_checkbox.isChecked())

    def _toggle_advanced_options_panel(self, checked=None):
        expanded = bool(checked) if checked is not None else bool(
            self.advanced_options_button.isChecked()
        )
        if hasattr(self, "advanced_options_panel"):
            self.advanced_options_panel.setVisible(expanded)
        if hasattr(self, "advanced_options_button"):
            self.advanced_options_button.setArrowType(
                Qt.DownArrow if expanded else Qt.RightArrow
            )
            if self.advanced_options_button.isChecked() != expanded:
                self.advanced_options_button.setChecked(expanded)

    def _effective_context_keys(self):
        if not self._advanced_context_enabled():
            neutral_key = neutral_context_key()
            return neutral_key, neutral_key
        return self.culture_combo.currentData(), self.period_combo.currentData()

    def _usage_goal_key(self):
        if not hasattr(self, "purpose_combo"):
            return "general"
        goal_key = self.purpose_combo.currentData()
        return goal_key if goal_key else "general"

    def _usage_goal_label(self, goal_key=None):
        if not hasattr(self, "purpose_combo"):
            return "general"
        target_key = goal_key or self._usage_goal_key()
        index = self.purpose_combo.findData(target_key)
        if index >= 0:
            return self.purpose_combo.itemText(index)
        return self.purpose_combo.currentText() or str(target_key)

    @classmethod
    def _goal_profile_key(cls, goal_key):
        return cls.GOAL_PROFILE_MAP.get(goal_key)

    @classmethod
    def _goal_key_for_profile(cls, profile_key):
        return cls.PROFILE_GOAL_MAP.get(profile_key, "custom")

    @staticmethod
    def _goal_include_terms(goal_key):
        return goal_key in ("tomb", "house")

    def _goal_hint_html(self, goal_key):
        profile_key = self._goal_profile_key(goal_key)
        if goal_key == "custom":
            profile_label_text = self.profile_combo.currentText() or ui_text(
                "goal_custom_label", default="직접 설정"
            )
            return ui_text(
                "goal_hint_custom",
                default=(
                    "<b>직접 설정</b> 모드입니다. 고급 옵션에서 프리셋, 문화권, 시대를 "
                    "직접 고르며 결과를 조정합니다."
                ),
            ).format(profile=escape(profile_label_text))

        profile_label_text = profile_label(profile_key, language_code())
        return ui_text(
            f"goal_hint_{goal_key}",
            default=(
                "<b>{goal}</b> 목적에 맞는 기본 프리셋을 자동 적용합니다. "
                "고급 옵션을 열지 않아도 '{profile}' 모델이 연결됩니다."
            ),
        ).format(
            goal=escape(self._usage_goal_label(goal_key)),
            profile=escape(profile_label_text or profile_key or ""),
        )

    def _guide_intro_html(self, goal_key):
        default_text = (
            "<b>이 모드가 하는 일</b><br/>DEM과 수계를 바탕으로 산줄기, 혈 후보, 구조 용어를 "
            "차례대로 읽습니다."
        )
        return ui_text(f"guide_goal_intro_{goal_key}", default=default_text)

    def _guide_steps_html(self, goal_key):
        default_text = (
            "<b>권장 순서</b><br/>"
            "1. DEM을 고릅니다.<br/>"
            "2. 수계를 넣거나 DEM 자동 수계를 사용합니다.<br/>"
            "3. 지형 추출을 먼저 실행합니다."
        )
        return ui_text(f"guide_goal_steps_{goal_key}", default=default_text)

    def _update_usage_goal_guidance(self):
        goal_key = self._usage_goal_key()
        if hasattr(self, "goal_hint_label"):
            self.goal_hint_label.setText(self._goal_hint_html(goal_key))
        if hasattr(self, "guide_intro_widget"):
            self.guide_intro_widget.setText(self._guide_intro_html(goal_key))
        if hasattr(self, "guide_steps_widget"):
            self.guide_steps_widget.setText(self._guide_steps_html(goal_key))

    def _apply_usage_goal_presets(self, *_args):
        if self._syncing_goal_controls:
            return

        goal_key = self._usage_goal_key()
        self._syncing_goal_controls = True
        try:
            profile_key = self._goal_profile_key(goal_key)
            if profile_key:
                profile_index = self.profile_combo.findData(profile_key)
                if profile_index >= 0 and profile_index != self.profile_combo.currentIndex():
                    self.profile_combo.setCurrentIndex(profile_index)

                if hasattr(self, "include_terms_checkbox"):
                    include_terms = self._goal_include_terms(goal_key)
                    if self.include_terms_checkbox.isChecked() != include_terms:
                        self.include_terms_checkbox.setChecked(include_terms)

                if hasattr(self, "mode_tabs") and self.mode_tabs.currentIndex() != 0:
                    self.mode_tabs.setCurrentIndex(0)

            if goal_key == "custom" and hasattr(self, "advanced_options_button"):
                self.advanced_options_button.setChecked(True)
        finally:
            self._syncing_goal_controls = False

        self._update_usage_goal_guidance()

    def _sync_usage_goal_from_profile(self, *_args):
        if self._syncing_goal_controls or not hasattr(self, "profile_combo"):
            self._update_usage_goal_guidance()
            return

        goal_key = self._goal_key_for_profile(self.profile_combo.currentData())
        index = self.purpose_combo.findData(goal_key)
        if index < 0:
            self._update_usage_goal_guidance()
            return

        self._syncing_goal_controls = True
        try:
            if index != self.purpose_combo.currentIndex():
                self.purpose_combo.setCurrentIndex(index)
        finally:
            self._syncing_goal_controls = False
        self._update_usage_goal_guidance()

    def _toggle_advanced_context_controls(self, *_args):
        enabled = self._advanced_context_enabled()
        widgets = [
            getattr(self, "culture_combo", None),
            getattr(self, "period_combo", None),
            getattr(self, "context_param_combo", None),
        ]
        for widget in widgets:
            if widget is not None:
                widget.setEnabled(enabled)
        self._update_context_evidence_hint()

    def _toggle_web_mountain_controls(self, *_args):
        enabled = self.mountain_name_enrichment_enabled()
        if hasattr(self, "web_mountain_lang_combo"):
            self.web_mountain_lang_combo.setEnabled(enabled)
        if hasattr(self, "web_mountain_radius_spin"):
            self.web_mountain_radius_spin.setEnabled(enabled)
        if hasattr(self, "web_mountain_limit_spin"):
            self.web_mountain_limit_spin.setEnabled(enabled)

    def mountain_name_enrichment_enabled(self):
        if not hasattr(self, "web_mountain_checkbox"):
            return False
        return bool(self.web_mountain_checkbox.isChecked())

    def mountain_name_radius_m(self):
        mountain_cfg = mountain_options()
        if not hasattr(self, "web_mountain_radius_spin"):
            return int(mountain_cfg["radius_default_m"])
        try:
            return int(self.web_mountain_radius_spin.value())
        except (TypeError, ValueError):
            return int(mountain_cfg["radius_default_m"])

    def mountain_name_max_features(self):
        mountain_cfg = mountain_options()
        if not hasattr(self, "web_mountain_limit_spin"):
            return int(mountain_cfg["max_features_default"])
        try:
            return int(self.web_mountain_limit_spin.value())
        except (TypeError, ValueError):
            return int(mountain_cfg["max_features_default"])

    def mountain_name_language_preference(self):
        mountain_cfg = mountain_options()
        if not hasattr(self, "web_mountain_lang_combo"):
            return str(mountain_cfg["language_default"])
        value = self.web_mountain_lang_combo.currentData()
        if value in ("local", "ko", "en"):
            return value
        return str(mountain_cfg["language_default"])

    def _open_help_dialog(self):
        if self._help_dialog is None:
            self._help_dialog = FengShuiHelpDialog(self)
        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()

    def _open_context_evidence_dialog(self):
        if self._advanced_context_enabled():
            culture_key, period_key = self._effective_context_keys()
            html = context_evidence_html(
                culture_key=culture_key,
                period_key=period_key,
                hemisphere=self.hemisphere_combo.currentData(),
                language=self.label_language(),
            )
        else:
            html = ui_text(
                "context_general_mode_dialog_html",
                default=(
                    "<h3>General Principles Mode</h3>"
                    "<p>Country/period overrides are disabled.</p>"
                    "<p>Enable advanced context to inspect regional/historical evidence tables.</p>"
                ),
            )
        if self._context_evidence_dialog is None:
            self._context_evidence_dialog = ContextEvidenceDialog(self)
        self._context_evidence_dialog.set_html(html)
        self._context_evidence_dialog.show()
        self._context_evidence_dialog.raise_()
        self._context_evidence_dialog.activateWindow()

    def _update_context_evidence_hint(self, *_args):
        if not self._advanced_context_enabled():
            self._context_records = []
            self.context_param_combo.blockSignals(True)
            self.context_param_combo.clear()
            self.context_param_combo.blockSignals(False)
            self.context_evidence_hint.setText(
                ui_text(
                    "context_general_mode_hint",
                    default=(
                        "General principles mode is active. Country/period biases are disabled. "
                        "Enable advanced context to apply regional and historical profiles."
                    ),
                )
            )
            self.context_param_hint.setText(
                ui_text(
                    "context_general_mode_note",
                    default="Using neutral global principles only (no country/period overrides).",
                )
            )
            self._update_evidence_summary_widget()
            return

        culture_key, period_key = self._effective_context_keys()
        records = context_evidence_records(
            culture_key=culture_key,
            period_key=period_key,
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
        hint = ui_text(
            "context_hint_template",
            default="Profile evidence: {culture} / {period} (details: '{button}').",
        ).format(
            culture=self.culture_combo.currentText(),
            period=self.period_combo.currentText(),
            button=ui_text("context_evidence_button", default="View Context Evidence"),
        )
        references_text = reference_display_text(source_list, limit=2)
        if references_text:
            prefix_default = (
                " 대표 참고문헌: "
                if language_code() == "ko"
                else " Representative references: "
            )
            hint += ui_text(
                "context_hint_reference_prefix",
                default=prefix_default,
            )
            hint += references_text
        self.context_evidence_hint.setText(hint)
        self._update_selected_param_evidence_hint()
        self._update_evidence_summary_widget()

    def _update_selected_param_evidence_hint(self, *_args):
        if not self._advanced_context_enabled():
            self.context_param_hint.setText(
                ui_text(
                    "context_general_mode_note",
                    default="Using neutral global principles only (no country/period overrides).",
                )
            )
            return

        if not self._context_records:
            self.context_param_hint.setText(
                ui_text("context_no_params", default="No parameter evidence.")
            )
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
        references_text = reference_display_text(item.get("source_doi", []))
        if not references_text:
            references_text = ui_text(
                "context_no_reference",
                default="참고문헌 없음" if language_code() == "ko" else "No reference",
            )
        note = item.get("note") or ui_text("context_no_note", default="No note")
        self.context_param_hint.setText(
            ui_text(
                "context_param_reference_template",
                default=(
                    "[{group}.{name}] 값={value} | 근거수준={level} | 참고문헌={reference} | 메모={note}"
                    if language_code() == "ko"
                    else (
                        "[{group}.{name}] value={value} | evidence={level} | "
                        "reference={reference} | note={note}"
                    )
                ),
            ).format(
                group=item.get("group", "-"),
                name=item.get("name", "-"),
                value=value_text,
                level=level,
                reference=references_text,
                note=note,
            )
        )

    def _update_metric_help_hint(self, *_args):
        description = self.metric_help_combo.currentData()
        if description in (None, ""):
            description = ui_text(
                "metric_help_empty",
                default="No description available for the selected metric.",
            )
        self.metric_help_hint.setText(str(description))

    def _update_quick_number_widget(self, *_args):
        if not hasattr(self, "quick_number_widget"):
            return
        self.quick_number_widget.setText(
            ui_text(
                "guide_quick_numbers_html",
                default=(
                    "<b>Quick Number Read</b><br/>"
                    "score/confidence (0-1): 0.80+ strong, 0.65-0.79 good, 0.50-0.64 moderate, below 0.50 weak.<br/>"
                    "TPI: near 0 flat, negative concave, positive convex."
                ),
            )
        )

    def _update_dem_diagnostics_hint(self, *_args):
        if not hasattr(self, "dem_diag_widget"):
            return

        dem_layer = self.dem_combo.currentLayer() if hasattr(self, "dem_combo") else None
        if dem_layer is None:
            self.dem_diag_widget.setText(
                ui_text(
                    "guide_dem_diag_empty",
                    default=(
                        "<b>DEM Diagnostics</b><br/>Select a DEM layer to inspect "
                        "resolution, CRS unit reliability, and sampling density."
                    ),
                )
            )
            return

        try:
            x_res = abs(float(dem_layer.rasterUnitsPerPixelX()))
            y_res = abs(float(dem_layer.rasterUnitsPerPixelY()))
        except (TypeError, ValueError):
            x_res = 0.0
            y_res = 0.0
        dem_step = (x_res + y_res) * 0.5 if x_res > 0 and y_res > 0 else max(x_res, y_res)

        extent = dem_layer.extent()
        width = max(0.0, float(extent.width()))
        height = max(0.0, float(extent.height()))

        rules = analysis_rules().get("adaptive_spacing", {})
        try:
            base_step_factor = float(rules.get("base_step_factor", 10.0))
            min_span_divisor = float(rules.get("min_span_divisor", 180.0))
        except (TypeError, ValueError):
            base_step_factor = 10.0
            min_span_divisor = 180.0
        min_span_divisor = max(1.0, min_span_divisor)
        min_span = min(width, height)
        spacing = max(dem_step * max(0.1, base_step_factor), min_span / min_span_divisor)
        if spacing <= 0:
            spacing = dem_step * 10.0 if dem_step > 0 else 1.0
        approx_cols = max(1, int(width / max(spacing, 1e-9)) + 1)
        approx_rows = max(1, int(height / max(spacing, 1e-9)) + 1)
        approx_nodes = approx_cols * approx_rows

        crs_mode = "geographic" if dem_layer.crs().isGeographic() else "projected"
        crs_note = (
            "distance/smoothing in degree units can distort interpretation"
            if crs_mode == "geographic"
            else "distance/smoothing in projected units is more reliable"
        )

        self.dem_diag_widget.setText(
            ui_text(
                "guide_dem_diag_template",
                default=(
                    "<b>DEM Diagnostics</b><br/>"
                    "layer={layer}<br/>"
                    "pixel_step={step:.4f}, extent={width:.1f} x {height:.1f}, "
                    "adaptive_spacing={spacing:.2f}, approx_sampling_nodes={nodes}<br/>"
                    "CRS mode={crs_mode}: {crs_note}"
                ),
            ).format(
                layer=escape(dem_layer.name()),
                step=dem_step,
                width=width,
                height=height,
                spacing=spacing,
                nodes=approx_nodes,
                crs_mode=crs_mode,
                crs_note=escape(crs_note),
            )
        )

    def _update_evidence_summary_widget(self, *_args):
        if not hasattr(self, "evidence_widget"):
            return
        if not self._advanced_context_enabled():
            self.evidence_widget.setText(
                ui_text(
                    "guide_evidence_general_mode",
                    default=(
                        "<b>Evidence Summary</b><br/>"
                        "General principles mode: region/period evidence is intentionally not applied."
                    ),
                )
            )
            return
        records = self._context_records if isinstance(self._context_records, list) else []
        if not records:
            self.evidence_widget.setText(
                ui_text(
                    "guide_evidence_empty",
                    default="<b>Evidence Summary</b><br/>No context evidence loaded.",
                )
            )
            return

        counts = {"A": 0, "B": 0, "C": 0, "U": 0}
        for item in records:
            level = str(item.get("evidence_level", "U")).upper()
            if level not in counts:
                level = "U"
            counts[level] += 1
        total = max(1, sum(counts.values()))
        low_count = counts["C"] + counts["U"]
        low_ratio = low_count / total
        if low_ratio >= 0.45:
            quality = "Exploratory"
        elif low_ratio >= 0.20:
            quality = "Moderate"
        else:
            quality = "Stronger"

        recommendation = (
            "Includes many heuristic priors (C/U); run calibration and local validation."
            if low_count > 0
            else "Mostly A/B evidence for this context."
        )
        self.evidence_widget.setText(
            ui_text(
                "guide_evidence_template",
                default=(
                    "<b>Evidence Summary</b><br/>"
                    "A={a}, B={b}, C={c}, U={u} (total={total})<br/>"
                    "quality={quality}<br/>"
                    "{recommendation}"
                ),
            ).format(
                a=counts["A"],
                b=counts["B"],
                c=counts["C"],
                u=counts["U"],
                total=total,
                quality=quality,
                recommendation=escape(recommendation),
            )
        )

    def _workflow_checks(self):
        dem_ready = self.dem_combo.currentLayer() is not None
        sites_ready = self.sites_combo.currentLayer() is not None
        water_ready = self.water_combo.currentLayer() is not None
        goal_key = self._usage_goal_key()
        terms_ready = (
            self.include_terms_checkbox.isChecked()
            if goal_key in ("tomb", "house")
            else True
        )

        if self.mode_tabs.currentIndex() == 1:
            hydro_ready = water_ready or self.analysis_auto_hydro_checkbox.isChecked()
            checks = [
                (ui_text("workflow_check_dem", default="Select DEM layer"), dem_ready),
                (ui_text("workflow_check_sites", default="Select candidate point layer"), sites_ready),
                (ui_text("workflow_check_hydro", default="Confirm hydro source"), hydro_ready),
                (
                    ui_text("workflow_check_analysis_ready", default="Ready to run analysis"),
                    dem_ready and sites_ready and hydro_ready,
                ),
            ]
            mode_name = tr("tab_analysis")
            action_name = tr("run_button")
        else:
            hydro_ready = water_ready or self.landscape_auto_hydro_checkbox.isChecked()
            checks = [
                (ui_text("workflow_check_dem", default="Select DEM layer"), dem_ready),
                (ui_text("workflow_check_hydro", default="Confirm hydro source"), hydro_ready),
                (
                    ui_text(
                        "workflow_check_terms_recommended",
                        default="Turn on term points for site-shape reading",
                    )
                    if goal_key in ("tomb", "house")
                    else ui_text(
                        "workflow_check_terms_option",
                        default="Check term point/link options",
                    ),
                    terms_ready,
                ),
                (
                    ui_text("workflow_check_extract_ready", default="Ready to run extraction"),
                    dem_ready and hydro_ready and terms_ready,
                ),
            ]
            mode_name = tr("tab_landscape")
            action_name = tr("extract_landscape_button")
        return mode_name, action_name, checks

    def _refresh_progress_guide(self, *_args):
        if not hasattr(self, "workflow_progress"):
            return

        mode_name, action_name, checks = self._workflow_checks()
        completed = sum(1 for _, done in checks if done)
        total = max(1, len(checks))
        percent = int(round((completed / total) * 100.0))
        self.workflow_progress.setValue(percent)
        self._update_usage_goal_guidance()
        lang_name = (
            ui_text("workflow_lang_ko", default="Korean")
            if self.label_language() == "ko"
            else ui_text("workflow_lang_en", default="English")
        )
        context_mode = (
            ui_text("context_mode_general_short", default="General")
            if not self._advanced_context_enabled()
            else ui_text("context_mode_advanced_short", default="Advanced")
        )
        mountain_mode = (
            ui_text("web_mountain_mode_on", default="On")
            if self.mountain_name_enrichment_enabled()
            else ui_text("web_mountain_mode_off", default="Off")
        )
        mountain_lang = self.mountain_name_language_preference()
        goal_name = self._usage_goal_label()
        profile_name = self.profile_combo.currentText() or str(self.profile_combo.currentData())
        self.progress_summary_label.setText(
            ui_text(
                "workflow_summary_template",
                default=(
                    "Goal: {goal} | Mode: {mode} | Model: {profile} | "
                    "Label language: {lang} | Context: {context_mode} | "
                    "Mountain names(web): {mountain_mode}/{mountain_lang} | "
                    "Readiness {percent}%"
                ),
            ).format(
                goal=goal_name,
                mode=mode_name,
                profile=profile_name,
                lang=lang_name,
                context_mode=context_mode,
                mountain_mode=mountain_mode,
                mountain_lang=mountain_lang,
                percent=percent,
            )
        )

        pending = next((label for label, done in checks if not done), None)
        if pending:
            self.next_step_label.setText(
                ui_text("workflow_next_template", default="Next step: {pending}").format(
                    pending=pending
                )
            )
        else:
            self.next_step_label.setText(
                ui_text(
                    "workflow_next_action_template",
                    default="Next step: run with '{action}' button.",
                ).format(action=action_name)
            )

        rows = []
        for label, done in checks:
            state = (
                ui_text("workflow_state_done", default="Done")
                if done
                else ui_text("workflow_state_pending", default="Pending")
            )
            color = "#1f6255" if done else "#8a6d3b"
            rows.append(
                f"<span style='color:{color};'><b>{state}</b></span> · {escape(label)}"
            )
        self.checklist_label.setText("<br/>".join(rows))
        self.workflow_status_label.setText(
            ui_text(
                "workflow_recent_status_template",
                default="Recent status: {text}",
            ).format(text=self.status_label.text())
        )

    def set_status(self, text):
        self.status_label.setText(text)
        if hasattr(self, "workflow_status_label"):
            self.workflow_status_label.setText(
                ui_text(
                    "workflow_recent_status_template",
                    default="Recent status: {text}",
                ).format(text=text)
            )
        self._refresh_progress_guide()

    def label_language(self):
        if not hasattr(self, "label_language_combo"):
            return "ko"
        code = self.label_language_combo.currentData()
        return code if code in ("ko", "en") else "ko"

    def _emit_run_requested(self):
        culture_key, period_key = self._effective_context_keys()
        self.run_requested.emit(
            self.sites_combo.currentLayer(),
            self.dem_combo.currentLayer(),
            self.water_combo.currentLayer(),
            self.hemisphere_combo.currentData(),
            self.profile_combo.currentData(),
            culture_key,
            period_key,
            self.analysis_auto_hydro_checkbox.isChecked(),
        )

    def _emit_terms_requested(self):
        culture_key, period_key = self._effective_context_keys()
        self.terms_requested.emit(
            self.dem_combo.currentLayer(),
            self.water_combo.currentLayer(),
            self.hemisphere_combo.currentData(),
            self.profile_combo.currentData(),
            culture_key,
            period_key,
            self.landscape_auto_hydro_checkbox.isChecked(),
            self.include_terms_checkbox.isChecked(),
        )

    def _emit_calibration_requested(self):
        culture_key, period_key = self._effective_context_keys()
        self.calibration_requested.emit(
            self.sites_combo.currentLayer(),
            self.dem_combo.currentLayer(),
            self.water_combo.currentLayer(),
            self.hemisphere_combo.currentData(),
            self.profile_combo.currentData(),
            culture_key,
            period_key,
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
            QFrame#advancedPanel {
                background: #fbf7ee;
                border: 1px solid #dccfb8;
                border-radius: 10px;
            }
            QFrame#tabCard {
                background: #fffdf9;
                border: 1px solid #ddd2bf;
                border-radius: 10px;
            }
            QFrame#guideCard {
                background: #f7f1e6;
                border: 1px solid #d6cab3;
                border-radius: 11px;
            }
            QLabel#guideTitle {
                color: #173736;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#guideSummary {
                color: #2a413b;
            }
            QLabel#guideNext {
                color: #204f45;
                font-weight: 600;
            }
            QLabel#guideChecklist {
                color: #2f3a38;
            }
            QLabel#metricHint {
                color: #2f3a38;
                font-size: 11px;
            }
            QLabel#guideWidget {
                color: #2f3a38;
                font-size: 11px;
                background: #fcf7ee;
                border: 1px solid #ddcfb7;
                border-radius: 8px;
                padding: 6px 8px;
            }
            QLabel#guideStatus {
                color: #38534c;
                font-size: 11px;
            }
            QProgressBar#workflowProgress {
                border: 1px solid #c8b89e;
                border-radius: 6px;
                background: #fffaf1;
                text-align: center;
                min-height: 20px;
            }
            QProgressBar#workflowProgress::chunk {
                background: #2d6258;
                border-radius: 5px;
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
            QLabel#goalHint {
                color: #2f3a38;
                font-size: 11px;
                background: #fcf7ee;
                border: 1px solid #ddcfb7;
                border-radius: 8px;
                padding: 6px 8px;
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
            QToolButton#advancedToggle {
                background: #f6f1e6;
                border: 1px solid #d2c5af;
                border-radius: 7px;
                padding: 6px 10px;
                font-weight: 600;
                text-align: left;
            }
            QToolButton#advancedToggle:hover {
                background: #ede4d3;
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

