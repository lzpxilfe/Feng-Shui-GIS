# -*- coding: utf-8 -*-
from html import escape

from qgis.PyQt.QtCore import QSettings, Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
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
from .locale import set_language_code
from .mountain_options import mountain_options
from .profile_catalog import (
    available_profiles,
    line_styles,
    point_styles,
    profile_label,
    term_label,
    term_label_ko,
)
from .dock_widget_state import restore_ui_state as restore_dock_ui_state
from .dock_widget_state import snapshot_ui_state as snapshot_dock_ui_state
from .dock_widget_advanced_fragment import build_advanced_options_fragment
from .dock_widget_fragments import build_workflow_guide_card
from .dock_widget_controls import advanced_context_control_state, mountain_control_state
from .dock_widget_mode_state import (
    advanced_options_panel_state,
    usage_goal_guidance_state,
    usage_goal_preset_state,
)
from .dock_widget_mode_fragments import build_analysis_tab, build_landscape_tab
from .dock_widget_presenters import (
    apply_workflow_presentation,
    build_dem_diagnostics_html,
    build_evidence_summary_html,
    metric_help_text,
    quick_number_html,
    workflow_recent_status_text,
)
from .dock_widget_viewmodel import (
    context_evidence_state,
    recommendation_state,
    workflow_presentation_state,
)
from .dock_widget_workflow import workflow_checks_state
from .reference_catalog import references_help_html
from .ui_catalog import (
    ui_help_html,
    ui_hydro_legend,
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
    def _line_legend_rows(language=None):
        lang = language if language else language_code()
        meanings = ui_term_meanings(lang)
        rows = []
        for term_id, style in line_styles().items():
            color, width = style
            rows.append(
                (
                    "<tr>"
                    f"<td>{escape(term_label(term_id, lang))}</td>"
                    f"<td>{escape(str(meanings.get(term_id, '')))}</td>"
                    f"<td><code>{escape(color)}</code></td>"
                    f"<td>{width:.1f}</td>"
                    "</tr>"
                )
            )
        return "".join(rows)

    @staticmethod
    def _point_legend_rows(language=None):
        lang = language if language else language_code()
        meanings = ui_term_meanings(lang)
        rows = []
        for term_id, style in point_styles().items():
            fill_color, size, _stroke_color, _stroke_width = style
            rows.append(
                (
                    "<tr>"
                    f"<td>{escape(term_label(term_id, lang))}</td>"
                    f"<td>{escape(str(meanings.get(term_id, '')))}</td>"
                    f"<td><code>{escape(fill_color)}</code></td>"
                    f"<td>{float(size):.1f}</td>"
                    "</tr>"
                )
            )
        return "".join(rows)

    @staticmethod
    def _ridge_legend_rows(language=None):
        lang = language if language else language_code()
        rows = []
        for item in ui_ridge_legend(lang):
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
    def _hydro_legend_rows(language=None):
        lang = language if language else language_code()
        rows = []
        for item in ui_hydro_legend(lang):
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
        lang = language_code()
        point_rows = self._point_legend_rows(lang)
        line_rows = self._line_legend_rows(lang)
        ridge_rows = self._ridge_legend_rows(lang)
        hydro_rows = self._hydro_legend_rows(lang)
        return ui_help_html(
            "symbols",
            point_rows=point_rows,
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
    compare_requested = pyqtSignal(object, object, object, str, str, str, str, str, bool)
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
        "settlement": "village",
        "general": "general",
    }
    PROFILE_GOAL_MAP = {
        "tomb": "tomb",
        "house": "house",
        "general": "general",
    }

    @classmethod
    def _resolved_goal_profile_map(cls):
        goal_profile_map = dict(cls.GOAL_PROFILE_MAP)
        for profile_key in available_profiles():
            goal_profile_map.setdefault(profile_key, profile_key)
        return goal_profile_map

    @classmethod
    def _resolved_profile_goal_map(cls):
        profile_goal_map = dict(cls.PROFILE_GOAL_MAP)
        for goal_key, profile_key in cls._resolved_goal_profile_map().items():
            profile_goal_map.setdefault(profile_key, goal_key)
        return profile_goal_map

    def __init__(self, parent=None):
        super().__init__(parent)
        saved_ui_language = str(
            QSettings().value("feng_shui_gis/ui_language", "") or ""
        ).strip()
        if saved_ui_language:
            set_language_code(saved_ui_language)
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle(tr("panel_title"))
        self.resize(640, 720)
        self.setMinimumSize(540, 560)
        self._help_dialog = None
        self._context_evidence_dialog = None
        self._context_records = []
        self._syncing_goal_controls = False
        self._rebuilding_ui = False
        self.setStyleSheet(self._main_stylesheet())
        self._build_ui()

    @staticmethod
    def _clear_layout(layout):
        while layout is not None and layout.count():
            item = layout.takeAt(0)
            child_layout = item.layout()
            child_widget = item.widget()
            if child_layout is not None:
                FengShuiDockWidget._clear_layout(child_layout)
            if child_widget is not None:
                child_widget.deleteLater()

    @staticmethod
    def _set_combo_data(combo, value):
        if combo is None:
            return
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _reset_transient_dialogs(self):
        for attr_name in ("_help_dialog", "_context_evidence_dialog"):
            dialog = getattr(self, attr_name, None)
            if dialog is not None:
                dialog.close()
                dialog.deleteLater()
                setattr(self, attr_name, None)

    def _snapshot_ui_state(self):
        return snapshot_dock_ui_state(self)

    def _persist_language_preferences(self, *_args):
        settings = QSettings()
        settings.setValue("feng_shui_gis/ui_language", self.ui_language())
        settings.setValue("feng_shui_gis/label_language", self.label_language())

    def _restore_ui_state(self, state):
        if not isinstance(state, dict):
            return
        restore_dock_ui_state(self, state, rebuild_culture_combo=self._rebuild_culture_combo)

        self._toggle_advanced_options_panel(
            bool(state.get("advanced_options_open", False))
        )
        self._toggle_advanced_context_controls()
        self._toggle_web_mountain_controls()
        self._update_usage_goal_guidance()
        self._update_context_evidence_hint()
        self._update_profile_recommendation_hint()
        self._update_metric_help_hint()
        self._update_quick_number_widget()
        self._update_dem_diagnostics_hint()
        self._update_evidence_summary_widget()
        self._refresh_progress_guide()

    def ui_language(self):
        if hasattr(self, "ui_language_combo"):
            code = self.ui_language_combo.currentData()
            if code in ("ko", "en"):
                return code
        code = language_code()
        return code if code in ("ko", "en") else "ko"

    def _apply_ui_language_choice(self, *_args):
        if self._rebuilding_ui or not hasattr(self, "ui_language_combo"):
            return
        next_language = self.ui_language_combo.currentData()
        if next_language not in ("ko", "en") or next_language == language_code():
            return
        state = self._snapshot_ui_state()
        state["ui_language"] = next_language
        set_language_code(next_language)
        self._persist_language_preferences()
        self._reset_transient_dialogs()
        self.setWindowTitle(tr("panel_title"))
        self._rebuilding_ui = True
        try:
            self._build_ui()
            self._restore_ui_state(state)
        finally:
            self._rebuilding_ui = False

    def _reload_profile_options(self, *_args):
        if self._rebuilding_ui:
            return
        state = self._snapshot_ui_state()
        self._reset_transient_dialogs()
        self._rebuilding_ui = True
        try:
            self._build_ui()
            self._restore_ui_state(state)
        finally:
            self._rebuilding_ui = False
        self.set_status(
            ui_text("reload_profiles_status", default="Reloaded local profile list.")
        )

    def _apply_recommended_profile(self, *_args):
        if self._rebuilding_ui or not hasattr(self, "profile_combo"):
            return
        state = self._recommendation_state()
        if not bool(state.get("can_apply_recommended")):
            return
        recommended_key = state.get("recommended_profile_key")
        if not recommended_key:
            return
        index = self.profile_combo.findData(recommended_key)
        if index < 0:
            return
        self.profile_combo.setCurrentIndex(index)
        self.set_status(
            ui_text(
                "recommended_profile_applied",
                default="Applied the recommended calibrated profile.",
            )
        )

    def _comparison_profile_keys(self):
        state = self._recommendation_state()
        return (
            state.get("comparison_base_key"),
            state.get("comparison_profile_key"),
        )

    def _emit_compare_requested(self):
        base_profile_key, compare_profile_key = self._comparison_profile_keys()
        if not base_profile_key or not compare_profile_key:
            return
        culture_key, period_key = self._effective_context_keys()
        self.compare_requested.emit(
            self.sites_combo.currentLayer(),
            self.dem_combo.currentLayer(),
            self.water_combo.currentLayer(),
            self.hemisphere_combo.currentData(),
            base_profile_key,
            compare_profile_key,
            culture_key,
            period_key,
            self.analysis_auto_hydro_checkbox.isChecked(),
        )

    def _recommended_local_profile_key(self):
        state = self._recommendation_state()
        return state.get("recommended_profile_key")

    def _recommendation_state(self):
        if not hasattr(self, "profile_combo"):
            return recommendation_state(None, None, None, ())
        culture_key, period_key = self._effective_context_keys()
        return recommendation_state(
            self.profile_combo.currentData(),
            culture_key,
            period_key,
            available_profiles(),
        )

    def _update_profile_recommendation_hint(self, *_args):
        if not hasattr(self, "profile_recommendation_hint"):
            return
        state = self._recommendation_state()
        if hasattr(self, "apply_recommended_profile_button"):
            self.apply_recommended_profile_button.setEnabled(
                bool(state.get("can_apply_recommended"))
            )
        if hasattr(self, "compare_profiles_button"):
            self.compare_profiles_button.setEnabled(
                bool(state.get("can_compare_recommended"))
            )

        guidance_key = state.get("guidance_key") or "recommended_profile_none"
        guidance_default = state.get("guidance_default") or (
            "No saved local calibrated profile exists for this context yet."
        )
        guidance_args = dict(state.get("guidance_args") or {})
        recommended_key = state.get("recommended_profile_key")
        if recommended_key and "profile" not in guidance_args:
            guidance_args["profile"] = profile_label(recommended_key, language_code())
        try:
            guidance_text = ui_text(
                guidance_key,
                default=guidance_default,
            ).format(**guidance_args)
        except (KeyError, TypeError):
            guidance_text = guidance_default
        self.profile_recommendation_hint.setText(guidance_text)

    def _build_ui(self):
        root_layout = self.layout()
        if root_layout is None:
            root_layout = QVBoxLayout(self)
        else:
            self._clear_layout(root_layout)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setWindowTitle(tr("panel_title"))

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
        self.sites_combo.setFilters(
            QgsMapLayerProxyModel.PointLayer | QgsMapLayerProxyModel.PolygonLayer
        )
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

        self.ui_language_combo = QComboBox(self)
        self.ui_language_combo.addItem(ui_text("language_ko", default="Korean"), "ko")
        self.ui_language_combo.addItem(ui_text("language_en", default="English"), "en")
        current_ui_language = language_code()
        if current_ui_language not in ("ko", "en"):
            current_ui_language = "ko"
        ui_language_index = self.ui_language_combo.findData(current_ui_language)
        self.ui_language_combo.setCurrentIndex(max(0, ui_language_index))
        form.addRow(
            ui_text("ui_language_label", default="UI Language"),
            self.ui_language_combo,
        )

        self.label_language_combo = QComboBox(self)
        self.label_language_combo.addItem(ui_text("language_ko", default="Korean"), "ko")
        self.label_language_combo.addItem(ui_text("language_en", default="English"), "en")
        saved_label_language = QSettings().value("feng_shui_gis/label_language")
        if saved_label_language is None:
            saved_label_language = current_ui_language
        else:
            saved_label_language = (
                str(saved_label_language).strip().lower()
                if saved_label_language is not None
                else current_ui_language
            )
        label_language_index = self.label_language_combo.findData(
            saved_label_language if saved_label_language in ("ko", "en") else "ko"
        )
        self.label_language_combo.setCurrentIndex(max(0, label_language_index))
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

        advanced_refs = build_advanced_options_fragment(
            self,
            on_open_context_evidence_dialog=self._open_context_evidence_dialog,
        )
        self.advanced_options_button = advanced_refs.advanced_options_button
        controls_layout.addWidget(self.advanced_options_button)

        self.advanced_options_panel = advanced_refs.advanced_options_panel
        self.profile_combo = advanced_refs.profile_combo
        self.reload_profiles_button = advanced_refs.reload_profiles_button
        self.advanced_context_checkbox = advanced_refs.advanced_context_checkbox
        self.show_experimental_context_checkbox = (
            advanced_refs.show_experimental_context_checkbox
        )
        self.culture_combo = advanced_refs.culture_combo
        self._rebuild_culture_combo()
        self.period_combo = advanced_refs.period_combo
        self.context_param_combo = advanced_refs.context_param_combo
        self.profile_recommendation_hint = advanced_refs.profile_recommendation_hint
        self.apply_recommended_profile_button = (
            advanced_refs.apply_recommended_profile_button
        )
        self.compare_profiles_button = advanced_refs.compare_profiles_button
        self.context_evidence_button = advanced_refs.context_evidence_button
        self.context_evidence_hint = advanced_refs.context_evidence_hint
        self.context_param_hint = advanced_refs.context_param_hint

        controls_layout.addWidget(self.advanced_options_panel)
        layout.addWidget(controls)

        self.culture_combo.currentIndexChanged.connect(self._update_context_evidence_hint)
        self.period_combo.currentIndexChanged.connect(self._update_context_evidence_hint)
        self.hemisphere_combo.currentIndexChanged.connect(self._update_context_evidence_hint)
        self.context_param_combo.currentIndexChanged.connect(self._update_selected_param_evidence_hint)
        self.purpose_combo.currentIndexChanged.connect(self._apply_usage_goal_presets)
        self.ui_language_combo.currentIndexChanged.connect(self._apply_ui_language_choice)
        self.ui_language_combo.currentIndexChanged.connect(self._persist_language_preferences)
        self.reload_profiles_button.clicked.connect(self._reload_profile_options)
        self.apply_recommended_profile_button.clicked.connect(self._apply_recommended_profile)
        self.compare_profiles_button.clicked.connect(self._emit_compare_requested)
        self.profile_combo.currentIndexChanged.connect(self._update_profile_recommendation_hint)
        self.culture_combo.currentIndexChanged.connect(self._update_profile_recommendation_hint)
        self.period_combo.currentIndexChanged.connect(self._update_profile_recommendation_hint)
        self.advanced_context_checkbox.toggled.connect(self._update_profile_recommendation_hint)
        self.advanced_context_checkbox.toggled.connect(self._toggle_advanced_context_controls)
        self.show_experimental_context_checkbox.toggled.connect(
            self._reload_profile_options
        )
        self.advanced_options_button.toggled.connect(self._toggle_advanced_options_panel)
        self.advanced_options_button.toggled.connect(self._refresh_progress_guide)
        self.web_mountain_checkbox.toggled.connect(self._toggle_web_mountain_controls)
        self.web_mountain_checkbox.toggled.connect(self._refresh_progress_guide)
        self.web_mountain_radius_spin.valueChanged.connect(self._refresh_progress_guide)
        self.web_mountain_limit_spin.valueChanged.connect(self._refresh_progress_guide)
        self.web_mountain_lang_combo.currentIndexChanged.connect(self._refresh_progress_guide)
        self._update_context_evidence_hint()
        self._update_profile_recommendation_hint()

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
        self.show_experimental_context_checkbox.toggled.connect(self._refresh_progress_guide)
        self.label_language_combo.currentIndexChanged.connect(self._update_quick_number_widget)
        self.label_language_combo.currentIndexChanged.connect(self._persist_language_preferences)

        self._toggle_advanced_options_panel(False)
        self._toggle_advanced_context_controls()
        self._toggle_web_mountain_controls()
        default_goal_index = self.purpose_combo.findData("general")
        if default_goal_index < 0:
            default_goal_index = max(0, self.purpose_combo.findData("tomb"))
        if default_goal_index < 0:
            default_goal_index = max(0, self.purpose_combo.findData("house"))
        self.purpose_combo.setCurrentIndex(default_goal_index)
        self._apply_usage_goal_presets()
        self._update_metric_help_hint()
        self._update_quick_number_widget()
        self._update_dem_diagnostics_hint()
        self._update_evidence_summary_widget()
        self._refresh_progress_guide()

    def _build_workflow_guide_card(self):
        card, refs = build_workflow_guide_card(self, self._update_metric_help_hint)
        self._workflow_guide_refs = refs
        self.progress_summary_label = refs.progress_summary_label
        self.guide_intro_widget = refs.guide_intro_widget
        self.guide_steps_widget = refs.guide_steps_widget
        self.workflow_progress = refs.workflow_progress
        self.next_step_label = refs.next_step_label
        self.checklist_label = refs.checklist_label
        self.metric_help_combo = refs.metric_help_combo
        self.metric_help_hint = refs.metric_help_hint
        self.quick_number_widget = refs.quick_number_widget
        self.dem_diag_widget = refs.dem_diag_widget
        self.evidence_widget = refs.evidence_widget
        self.workflow_status_label = refs.workflow_status_label
        return card

    def _build_landscape_tab(self):
        tab, refs = build_landscape_tab(
            self,
            on_extract_terms_requested=self._emit_terms_requested,
        )
        self.landscape_auto_hydro_checkbox = refs.landscape_auto_hydro_checkbox
        self.include_terms_checkbox = refs.include_terms_checkbox
        self.extract_terms_button = refs.extract_terms_button
        return tab

    def _build_analysis_tab(self):
        tab, refs = build_analysis_tab(
            self,
            on_run_requested=self._emit_run_requested,
            on_calibration_requested=self._emit_calibration_requested,
        )
        self.analysis_auto_hydro_checkbox = refs.analysis_auto_hydro_checkbox
        self.negative_ratio_combo = refs.negative_ratio_combo
        self.calibration_seed_spin = refs.calibration_seed_spin
        self.run_button = refs.run_button
        self.calibration_button = refs.calibration_button
        return tab

    def _advanced_context_enabled(self):
        if not hasattr(self, "advanced_context_checkbox"):
            return False
        return bool(self.advanced_context_checkbox.isChecked())

    def _show_experimental_contexts(self):
        if not hasattr(self, "show_experimental_context_checkbox"):
            return False
        return bool(self.show_experimental_context_checkbox.isChecked())

    def _rebuild_culture_combo(self, selected_key=None):
        if not hasattr(self, "culture_combo"):
            return
        try:
            lang = self.ui_language()
        except (AttributeError, TypeError):
            lang = language_code()
        if selected_key is None:
            selected_key = self.culture_combo.currentData()

        stable_cultures = list(available_cultures("stable"))
        experimental_cultures = list(available_cultures("experimental"))
        self.culture_combo.blockSignals(True)
        self.culture_combo.clear()
        for culture_key in stable_cultures or ["east_asia"]:
            self.culture_combo.addItem(culture_label(culture_key, lang), culture_key)

        if self._show_experimental_contexts():
            for culture_key in experimental_cultures:
                if culture_key in stable_cultures:
                    continue
                suffix = " (실험적)" if lang == "ko" else " (Exploratory)"
                self.culture_combo.addItem(
                    f"{culture_label(culture_key, lang)}{suffix}",
                    culture_key,
                )

        self._set_combo_data(self.culture_combo, selected_key)
        if self.culture_combo.currentIndex() < 0 and self.culture_combo.count() > 0:
            self.culture_combo.setCurrentIndex(0)
        self.culture_combo.blockSignals(False)

    def _toggle_advanced_options_panel(self, checked=None):
        expanded = bool(checked) if checked is not None else bool(
            self.advanced_options_button.isChecked()
        )
        state = advanced_options_panel_state(expanded)
        if hasattr(self, "advanced_options_panel"):
            self.advanced_options_panel.setVisible(state["panel_visible"])
        if hasattr(self, "advanced_options_button"):
            self.advanced_options_button.setArrowType(
                Qt.DownArrow if state["arrow"] == "down" else Qt.RightArrow
            )
            if self.advanced_options_button.isChecked() != state["button_checked"]:
                self.advanced_options_button.setChecked(state["button_checked"])

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
        return cls._resolved_goal_profile_map().get(goal_key)

    @classmethod
    def _goal_key_for_profile(cls, profile_key):
        return cls._resolved_profile_goal_map().get(profile_key, "custom")

    @staticmethod
    def _goal_include_terms(goal_key):
        return goal_key in ("tomb", "house", "settlement")

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
        profile_key = self._goal_profile_key(goal_key)
        if goal_key == "custom":
            profile_label_text = self.profile_combo.currentText() or ui_text(
                "goal_custom_label", default="직접 설정"
            )
        elif profile_key:
            profile_label_text = profile_label(profile_key, language_code())
        else:
            current_profile = self.profile_combo.currentData()
            profile_label_text = (
                profile_label(current_profile, language_code())
                if current_profile
                else ""
            )
        guidance = usage_goal_guidance_state(
            goal_key,
            goal_label=self._usage_goal_label(goal_key),
            profile_label_text=profile_label_text or profile_key or "",
            custom_hint_template=ui_text(
                "goal_hint_custom",
                default=(
                    "<b>직접 설정</b> 모드입니다. 고급 옵션에서 프리셋, 문화권, 시대를 "
                    "직접 고르며 결과를 조정합니다."
                ),
            ),
            default_hint_template=ui_text(
                f"goal_hint_{goal_key}",
                default=(
                    "<b>{goal}</b> 목적에 맞는 기본 프리셋을 자동 적용합니다. "
                    "고급 옵션을 열지 않아도 '{profile}' 모델이 연결됩니다."
                ),
            ),
            guide_intro_html=self._guide_intro_html(goal_key),
            guide_steps_html=self._guide_steps_html(goal_key),
        )
        if hasattr(self, "goal_hint_label"):
            self.goal_hint_label.setText(guidance["goal_hint_html"])
        if hasattr(self, "guide_intro_widget"):
            self.guide_intro_widget.setText(guidance["guide_intro_html"])
        if hasattr(self, "guide_steps_widget"):
            self.guide_steps_widget.setText(guidance["guide_steps_html"])

    def _apply_usage_goal_presets(self, *_args):
        if self._syncing_goal_controls:
            return

        goal_key = self._usage_goal_key()
        self._syncing_goal_controls = True
        try:
            profile_key = self._goal_profile_key(goal_key)
            state = usage_goal_preset_state(
                goal_key,
                profile_key=profile_key,
                include_terms=self._goal_include_terms(goal_key),
            )
            if state["profile_key"]:
                profile_index = self.profile_combo.findData(state["profile_key"])
                if profile_index >= 0 and profile_index != self.profile_combo.currentIndex():
                    self.profile_combo.setCurrentIndex(profile_index)

                if hasattr(self, "include_terms_checkbox"):
                    if self.include_terms_checkbox.isChecked() != state["include_terms"]:
                        self.include_terms_checkbox.setChecked(state["include_terms"])

                if hasattr(self, "mode_tabs") and state["force_analysis_tab"] and self.mode_tabs.currentIndex() != 0:
                    self.mode_tabs.setCurrentIndex(0)

            if state["expand_advanced"] and hasattr(self, "advanced_options_button"):
                self._toggle_advanced_options_panel(True)
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
            index = self.purpose_combo.findData("custom")
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
        state = advanced_context_control_state(self._advanced_context_enabled())
        if hasattr(self, "culture_combo"):
            self.culture_combo.setEnabled(state["culture_combo_enabled"])
        if hasattr(self, "period_combo"):
            self.period_combo.setEnabled(state["period_combo_enabled"])
        if hasattr(self, "context_param_combo"):
            self.context_param_combo.setEnabled(state["context_param_combo_enabled"])
        if hasattr(self, "show_experimental_context_checkbox"):
            self.show_experimental_context_checkbox.setEnabled(
                state["show_experimental_contexts_enabled"]
            )
        self._update_context_evidence_hint()

    def _toggle_web_mountain_controls(self, *_args):
        state = mountain_control_state(self.mountain_name_enrichment_enabled())
        if hasattr(self, "web_mountain_lang_combo"):
            self.web_mountain_lang_combo.setEnabled(state["language_enabled"])
        if hasattr(self, "web_mountain_radius_spin"):
            self.web_mountain_radius_spin.setEnabled(state["radius_enabled"])
        if hasattr(self, "web_mountain_limit_spin"):
            self.web_mountain_limit_spin.setEnabled(state["limit_enabled"])

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
                language=self.ui_language(),
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
        culture_key, period_key = self._effective_context_keys()
        records = []
        if self._advanced_context_enabled():
            records = context_evidence_records(
                culture_key=culture_key,
                period_key=period_key,
                hemisphere=self.hemisphere_combo.currentData(),
            )
        state = context_evidence_state(
            advanced_context_enabled=self._advanced_context_enabled(),
            culture_key=culture_key,
            culture_name=self.culture_combo.currentText(),
            period_name=self.period_combo.currentText(),
            ui_language=self.ui_language(),
            records=records,
            selected_index=self.context_param_combo.currentData(),
        )
        self._context_records = state["records"]
        self.context_param_combo.blockSignals(True)
        self.context_param_combo.clear()
        for item in state["combo_items"]:
            self.context_param_combo.addItem(item["label"], item["data"])
        if state["selected_index"] >= 0:
            self.context_param_combo.setCurrentIndex(state["selected_index"])
        self.context_param_combo.blockSignals(False)
        self.context_evidence_hint.setText(state["hint_text"])
        self.context_param_hint.setText(state["param_hint_text"])
        self._update_evidence_summary_widget()

    def _update_selected_param_evidence_hint(self, *_args):
        culture_key, _period_key = self._effective_context_keys()
        state = context_evidence_state(
            advanced_context_enabled=self._advanced_context_enabled(),
            culture_key=culture_key,
            culture_name=self.culture_combo.currentText(),
            period_name=self.period_combo.currentText(),
            ui_language=self.ui_language(),
            records=self._context_records,
            selected_index=self.context_param_combo.currentIndex(),
        )
        self.context_param_hint.setText(state["param_hint_text"])

    def _update_metric_help_hint(self, *_args):
        self.metric_help_hint.setText(
            metric_help_text(self.metric_help_combo.currentData())
        )

    def _update_quick_number_widget(self, *_args):
        if not hasattr(self, "quick_number_widget"):
            return
        self.quick_number_widget.setText(quick_number_html())

    def _update_dem_diagnostics_hint(self, *_args):
        if not hasattr(self, "dem_diag_widget"):
            return

        dem_layer = self.dem_combo.currentLayer() if hasattr(self, "dem_combo") else None
        self.dem_diag_widget.setText(build_dem_diagnostics_html(dem_layer=dem_layer))

    def _update_evidence_summary_widget(self, *_args):
        if not hasattr(self, "evidence_widget"):
            return
        culture_key, _period_key = self._effective_context_keys()
        self.evidence_widget.setText(
            build_evidence_summary_html(
                records=self._context_records,
                advanced_context_enabled=self._advanced_context_enabled(),
                culture_key=culture_key,
            )
        )

    def _workflow_checks(self):
        return workflow_checks_state(
            mode_tab_index=self.mode_tabs.currentIndex(),
            goal_key=self._usage_goal_key(),
            dem_ready=self.dem_combo.currentLayer() is not None,
            sites_ready=self.sites_combo.currentLayer() is not None,
            water_ready=self.water_combo.currentLayer() is not None,
            analysis_auto_hydro=self.analysis_auto_hydro_checkbox.isChecked(),
            landscape_auto_hydro=self.landscape_auto_hydro_checkbox.isChecked(),
            include_terms=self.include_terms_checkbox.isChecked(),
        )

    def _refresh_progress_guide(self, *_args):
        if not hasattr(self, "workflow_progress"):
            return

        mode_name, action_name, checks = self._workflow_checks()
        self._update_usage_goal_guidance()
        state = workflow_presentation_state(
            mode_name=mode_name,
            action_name=action_name,
            checks=checks,
            goal_name=self._usage_goal_label(),
            profile_name=self.profile_combo.currentText() or str(self.profile_combo.currentData()),
            label_language=self.label_language(),
            advanced_context_enabled=self._advanced_context_enabled(),
            mountain_enabled=self.mountain_name_enrichment_enabled(),
            mountain_language=self.mountain_name_language_preference(),
            status_text=self.status_label.text(),
        )
        apply_workflow_presentation(self._workflow_guide_refs, state)

    def set_status(self, text):
        self.status_label.setText(text)
        if hasattr(self, "workflow_status_label"):
            self.workflow_status_label.setText(workflow_recent_status_text(text))
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

