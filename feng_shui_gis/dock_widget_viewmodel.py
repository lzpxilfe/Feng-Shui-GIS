# -*- coding: utf-8 -*-
"""View-model helpers for dock-widget decision state."""

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

from .cultural_context import neutral_context_key
from .locale import language_code
from .profile_catalog import profile_label
from .ui_catalog import ui_text


@dataclass(frozen=True)
class ProfileRecommendationState:
    current_profile_key: Optional[str]
    recommended_profile_key: Optional[str]
    comparison_base_key: Optional[str]
    comparison_profile_key: Optional[str]
    guidance_key: str
    guidance_default: str
    guidance_args: Dict[str, str]
    can_apply_recommended: bool
    can_compare_recommended: bool


@dataclass(frozen=True)
class WorkflowCheckItem:
    label_key: str
    label_default: str
    done: bool


@dataclass(frozen=True)
class WorkflowGuideState:
    mode_label_key: str
    mode_label_default: str
    action_label_key: str
    action_label_default: str
    checks: Tuple[WorkflowCheckItem, ...]
    done_count: int
    total_count: int
    percent: int


@dataclass(frozen=True)
class WorkflowCheckDisplayItem:
    label: str
    done: bool


@dataclass(frozen=True)
class WorkflowPresentationState:
    mode_name: str
    action_name: str
    checks: Tuple[WorkflowCheckDisplayItem, ...]
    percent: int
    next_step_text: str
    summary_text: str
    status_text: str


class DockWidgetProfileViewModel:
    @staticmethod
    def _normalize(value):
        if value is None:
            return ""
        text = str(value).strip()
        return text.lower()

    @classmethod
    def _effective_context(cls, advanced_context_enabled, culture_key, period_key):
        if not advanced_context_enabled:
            neutral_key = neutral_context_key()
            return neutral_key, neutral_key
        return cls._normalize(culture_key), cls._normalize(period_key)

    @classmethod
    def recommendation_state_payload(
        cls,
        *,
        current_profile_key,
        advanced_context_enabled,
        culture_key,
        period_key,
        available_profile_keys: Iterable[str],
        ui_language: str = None,
    ) -> Dict[str, object]:
        normalized_language = language_code()
        if ui_language:
            normalized_language = cls._normalize(ui_language) or normalized_language
        state = cls.recommendation_state(
            current_profile_key=current_profile_key,
            advanced_context_enabled=advanced_context_enabled,
            culture_key=culture_key,
            period_key=period_key,
            available_profile_keys=available_profile_keys,
        )
        recommended_profile_key = state.recommended_profile_key
        recommendation_label = ""
        if recommended_profile_key:
            recommendation_label = profile_label(
                recommended_profile_key,
                normalized_language or "ko",
            )
        guidance_args = dict(state.guidance_args)
        if "{profile}" in state.guidance_default and "{profile}" not in guidance_args:
            guidance_args["profile"] = recommendation_label
        guidance_text = ""
        if state.guidance_key:
            guidance_text = ui_text(
                state.guidance_key,
                normalized_language,
                default=state.guidance_default,
            )
            if guidance_args:
                try:
                    guidance_text = guidance_text.format(**guidance_args)
                except (KeyError, IndexError, ValueError):
                    guidance_text = guidance_text
        return {
            "state": state,
            "can_apply_recommended": state.can_apply_recommended,
            "can_compare_recommended": state.can_compare_recommended,
            "guidance_text": guidance_text,
        }

    @classmethod
    def workflow_state(
        cls,
        *,
        mode_tab_index,
        goal_key,
        dem_ready,
        sites_ready,
        water_ready,
        include_terms_enabled,
        analysis_auto_hydro,
        landscape_auto_hydro,
    ) -> WorkflowGuideState:
        goal_norm = cls._normalize(goal_key)
        terms_required = goal_norm in {"tomb", "house", "settlement"}
        checks = []

        if mode_tab_index == 1:
            hydro_ready = bool(water_ready or analysis_auto_hydro)
            checks.extend(
                [
                    WorkflowCheckItem(
                        "workflow_check_dem",
                        "Select DEM layer",
                        bool(dem_ready),
                    ),
                    WorkflowCheckItem(
                        "workflow_check_sites",
                        "Select candidate point layer",
                        bool(sites_ready),
                    ),
                    WorkflowCheckItem(
                        "workflow_check_hydro",
                        "Confirm hydro source",
                        bool(hydro_ready),
                    ),
                    WorkflowCheckItem(
                        "workflow_check_analysis_ready",
                        "Ready to run analysis",
                        bool(dem_ready and sites_ready and hydro_ready),
                    ),
                ]
            )
            mode_label_key = "tab_analysis"
            mode_label_default = "Analysis"
            action_label_key = "run_button"
            action_label_default = "Run Feng Shui Analysis"
        else:
            hydro_ready = bool(water_ready or landscape_auto_hydro)
            checks.extend(
                [
                    WorkflowCheckItem(
                        "workflow_check_dem",
                        "Select DEM layer",
                        bool(dem_ready),
                    ),
                    WorkflowCheckItem(
                        "workflow_check_hydro",
                        "Confirm hydro source",
                        bool(hydro_ready),
                    ),
                    WorkflowCheckItem(
                        "workflow_check_terms_recommended"
                        if terms_required
                        else "workflow_check_terms_option",
                        (
                            "Turn on term points for site-shape reading"
                            if terms_required
                            else "Check term point/link options"
                        ),
                        bool(include_terms_enabled if terms_required else True),
                    ),
                    WorkflowCheckItem(
                        "workflow_check_extract_ready",
                        "Ready to run extraction",
                        bool(
                            dem_ready
                            and hydro_ready
                            and (include_terms_enabled or not terms_required)
                        ),
                    ),
                ]
            )
            mode_label_key = "tab_landscape"
            mode_label_default = "Landscape"
            action_label_key = "extract_landscape_button"
            action_label_default = "Extract Landscape Features"

        total_checks = max(1, len(checks))
        completed = sum(1 for item in checks if item.done)
        percent = int(round((completed / float(total_checks)) * 100.0))
        return WorkflowGuideState(
            mode_label_key=mode_label_key,
            mode_label_default=mode_label_default,
            action_label_key=action_label_key,
            action_label_default=action_label_default,
            checks=tuple(checks),
            done_count=completed,
            total_count=total_checks,
            percent=percent,
        )

    @classmethod
    def workflow_presentation_state(
        cls,
        *,
        mode_tab_index,
        goal_key,
        dem_ready,
        sites_ready,
        water_ready,
        include_terms_enabled,
        analysis_auto_hydro,
        landscape_auto_hydro,
        ui_language,
        label_language,
        workflow_mode,
        advanced_context_enabled,
        mountain_name_enrichment_enabled,
        mountain_language_preference,
        goal_name,
        profile_name,
        recent_status,
        is_running,
        running_task_label,
    ) -> WorkflowPresentationState:
        state = cls.workflow_state(
            mode_tab_index=mode_tab_index,
            goal_key=goal_key,
            dem_ready=dem_ready,
            sites_ready=sites_ready,
            water_ready=water_ready,
            include_terms_enabled=include_terms_enabled,
            analysis_auto_hydro=analysis_auto_hydro,
            landscape_auto_hydro=landscape_auto_hydro,
        )
        mode_name = ui_text(
            state.mode_label_key,
            ui_language,
            default=state.mode_label_default,
        )
        action_name = ui_text(
            state.action_label_key,
            ui_language,
            default=state.action_label_default,
        )
        checks = tuple(
            WorkflowCheckDisplayItem(
                label=ui_text(item.label_key, ui_language, default=item.label_default),
                done=bool(item.done),
            )
            for item in state.checks
        )
        pending = next((item.label for item in checks if not item.done), None)
        if is_running:
            next_step_text = ui_text(
                "workflow_running_next_template",
                ui_language,
                default="Running now: {action}. You can cancel from this panel if needed.",
            ).format(
                action=(
                    str(running_task_label or "").strip()
                    or ui_text("workflow_running_default_label", ui_language, default="workflow")
                )
            )
        elif pending:
            next_step_text = ui_text(
                "workflow_next_template",
                ui_language,
                default="Next step: {pending}",
            ).format(pending=pending)
        else:
            next_step_text = ui_text(
                "workflow_next_action_template",
                ui_language,
                default="Next step: run with '{action}' button.",
            ).format(action=action_name)

        lang_name = (
            ui_text("workflow_lang_ko", ui_language, default="Korean")
            if label_language == "ko"
            else ui_text("workflow_lang_en", ui_language, default="English")
        )
        workflow_mode_key = str(workflow_mode or "quick").strip().lower()
        if workflow_mode_key == "basic":
            workflow_mode_key = "quick"
        elif workflow_mode_key == "expert":
            workflow_mode_key = "research"
        mode_label_keys = {
            "quick": ("workflow_mode_quick_short", "Quick"),
            "research": ("workflow_mode_research_short", "Research"),
            "developer": ("workflow_mode_developer_short", "Developer"),
        }
        mode_label_key, mode_default = mode_label_keys.get(
            workflow_mode_key,
            ("workflow_mode_quick_short", "Quick"),
        )
        workflow_mode_name = ui_text(mode_label_key, ui_language, default=mode_default)
        context_mode_name = (
            ui_text("context_mode_advanced_short", ui_language, default="Advanced")
            if advanced_context_enabled
            else ui_text("context_mode_general_short", ui_language, default="General")
        )
        mountain_mode_name = (
            ui_text("web_mountain_mode_on", ui_language, default="On")
            if mountain_name_enrichment_enabled
            else ui_text("web_mountain_mode_off", ui_language, default="Off")
        )
        summary_text = ui_text(
            "workflow_summary_template",
            ui_language,
            default=(
                "Goal: {goal} | Mode: {mode} | Model: {profile} | "
                "Workflow: {workflow_mode} | Label language: {lang} | "
                "Context: {context_mode} | "
                "Mountain names(web): {mountain_mode}/{mountain_lang} | "
                "Readiness {percent}%"
            ),
        ).format(
            goal=goal_name,
            mode=mode_name,
            profile=profile_name,
            workflow_mode=workflow_mode_name,
            lang=lang_name,
            context_mode=context_mode_name,
            mountain_mode=mountain_mode_name,
            mountain_lang=mountain_language_preference,
            percent=state.percent,
        )
        if is_running:
            status_text = ui_text(
                "workflow_status_running_template",
                ui_language,
                default="Running: {action}.",
            ).format(
                action=(
                    str(running_task_label or "").strip()
                    or ui_text("workflow_running_default_label", ui_language, default="workflow")
                )
            )
            summary_text = summary_text + " | " + ui_text(
                "workflow_running_summary_suffix",
                ui_language,
                default="Status: running",
            )
        else:
            status_text = ui_text(
                "workflow_recent_status_template",
                ui_language,
                default="Recent status: {text}",
            ).format(text=recent_status)
        return WorkflowPresentationState(
            mode_name=mode_name,
            action_name=action_name,
            checks=checks,
            percent=state.percent,
            next_step_text=next_step_text,
            summary_text=summary_text,
            status_text=status_text,
        )

    @classmethod
    def recommendation_state(
        cls,
        current_profile_key,
        advanced_context_enabled,
        culture_key,
        period_key,
        available_profile_keys: Iterable[str],
    ) -> ProfileRecommendationState:
        current_text = cls._normalize(current_profile_key)
        if not current_text:
            return ProfileRecommendationState(
                current_profile_key=None,
                recommended_profile_key=None,
                comparison_base_key=None,
                comparison_profile_key=None,
                guidance_key="",
                guidance_default="",
                guidance_args={},
                can_apply_recommended=False,
                can_compare_recommended=False,
            )
        current_profile_key = str(current_profile_key)
        available_keys = {cls._normalize(key) for key in available_profile_keys}

        recommended_profile_key = cls.recommended_profile_key(
            current_profile_key,
            advanced_context_enabled,
            culture_key,
            period_key,
            available_keys,
        )

        comparison_base_key = None
        comparison_profile_key = None
        if recommended_profile_key and recommended_profile_key != current_profile_key:
            comparison_base_key = current_profile_key
            comparison_profile_key = recommended_profile_key
            return ProfileRecommendationState(
                current_profile_key=current_profile_key,
                recommended_profile_key=recommended_profile_key,
                comparison_base_key=comparison_base_key,
                comparison_profile_key=comparison_profile_key,
                guidance_key="recommended_profile_hint_template",
                guidance_default="Recommended calibrated profile: {profile} ({key})",
                guidance_args={
                    "profile": str(recommended_profile_key),
                    "key": recommended_profile_key,
                },
                can_apply_recommended=True,
                can_compare_recommended=True,
            )
        if recommended_profile_key == current_profile_key:
            return ProfileRecommendationState(
                current_profile_key=current_profile_key,
                recommended_profile_key=recommended_profile_key,
                comparison_base_key=comparison_base_key,
                comparison_profile_key=comparison_profile_key,
                guidance_key="recommended_profile_active_template",
                guidance_default="Using the recommended calibrated profile: {profile}",
                guidance_args={"profile": str(recommended_profile_key)},
                can_apply_recommended=False,
                can_compare_recommended=False,
            )

        elif "_cal_" in current_text:
            culture_effective, period_effective = cls._effective_context(
                advanced_context_enabled,
                culture_key,
                period_key,
            )
            suffix = f"_{culture_effective}_{period_effective}_cal_"
            index = current_text.find(suffix)
            if index > 0:
                base_profile_key = current_profile_key[:index]
                if cls._normalize(base_profile_key) in available_keys:
                    comparison_base_key = base_profile_key
                    comparison_profile_key = current_profile_key
                    return ProfileRecommendationState(
                        current_profile_key=current_profile_key,
                        recommended_profile_key=recommended_profile_key,
                        comparison_base_key=comparison_base_key,
                        comparison_profile_key=comparison_profile_key,
                        guidance_key="recommended_profile_active_template",
                        guidance_default="Using the recommended calibrated profile: {profile}",
                        guidance_args={"profile": comparison_profile_key},
                        can_apply_recommended=False,
                        can_compare_recommended=True,
                    )

        if comparison_base_key and comparison_profile_key:
            return ProfileRecommendationState(
                current_profile_key=current_profile_key,
                recommended_profile_key=recommended_profile_key,
                comparison_base_key=comparison_base_key,
                comparison_profile_key=comparison_profile_key,
                guidance_key="recommended_profile_compare_only",
                guidance_default="You can run a quick comparison between the calibrated profile and its base preset.",
                guidance_args={},
                can_apply_recommended=False,
                can_compare_recommended=True,
            )

        return ProfileRecommendationState(
            current_profile_key=current_profile_key,
            recommended_profile_key=recommended_profile_key,
            comparison_base_key=comparison_base_key,
            comparison_profile_key=comparison_profile_key,
            guidance_key="recommended_profile_none",
            guidance_default="No saved local calibrated profile exists for this context yet.",
            guidance_args={},
            can_apply_recommended=False,
            can_compare_recommended=False,
        )

    @classmethod
    def recommended_profile_key(
        cls,
        current_profile_key,
        advanced_context_enabled,
        culture_key,
        period_key,
        available_profile_keys: Iterable[str],
    ):
        normalized_current = cls._normalize(current_profile_key)
        if not normalized_current:
            return None
        if "_cal_" in normalized_current:
            return str(current_profile_key)

        available_keys = {
            str(key)
            for key in available_profile_keys
            if str(key).strip()
        }
        culture_effective, period_effective = cls._effective_context(
            advanced_context_enabled,
            culture_key,
            period_key,
        )
        prefix = f"{str(current_profile_key)}_{culture_effective}_{period_effective}_cal_".lower()
        candidates = [
            key
            for key in available_keys
            if str(key).lower().startswith(prefix)
        ]
        if not candidates:
            return None
        return sorted(candidates)[-1]
