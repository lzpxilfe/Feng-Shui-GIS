#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Pure policy helpers for dock-widget recommendation decisions."""

from html import escape

from .cultural_context import culture_visibility_tier
from .reference_catalog import reference_display_text
from .ui_catalog import ui_text


def _to_profile_key(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _find_available_profile(profile_key, available_profiles):
    target = _to_profile_key(profile_key)
    if target is None:
        return None
    for candidate in available_profiles or []:
        if _to_profile_key(candidate) == target:
            return candidate
    return None


def recommended_calibrated_profile(current_profile_key, culture_key, period_key, available_profiles):
    current_profile_key = _to_profile_key(current_profile_key)
    culture_key = _to_profile_key(culture_key)
    period_key = _to_profile_key(period_key)
    if not current_profile_key or not culture_key or not period_key:
        return None
    if "_cal_" in current_profile_key.lower():
        return current_profile_key
    prefix = f"{current_profile_key}_{culture_key}_{period_key}_cal_".lower()
    candidates = [
        profile_key
        for profile_key in (available_profiles or [])
        if _to_profile_key(profile_key) and str(profile_key).lower().startswith(prefix)
    ]
    if not candidates:
        return None
    return sorted(candidates)[-1]


def comparison_profile_pair(current_profile_key, culture_key, period_key, available_profiles):
    """Return (base_profile, compare_profile) when a safe deterministic pair is available."""
    current_profile_key = _to_profile_key(current_profile_key)
    if not current_profile_key:
        return None, None

    recommended = recommended_calibrated_profile(
        current_profile_key,
        culture_key,
        period_key,
        available_profiles,
    )
    if recommended and _to_profile_key(recommended) != current_profile_key:
        return current_profile_key, recommended

    culture_key = _to_profile_key(culture_key)
    period_key = _to_profile_key(period_key)
    if not culture_key or not period_key:
        return None, None

    lower_current = current_profile_key.lower()
    suffix = f"_{culture_key}_{period_key}_cal_"
    lower_suffix = suffix.lower()
    marker = lower_current.find(lower_suffix)
    if marker <= 0:
        return None, None
    base_profile_key = current_profile_key[:marker]
    if not _find_available_profile(base_profile_key, available_profiles):
        return None, None
    return base_profile_key, current_profile_key


def recommendation_state(current_profile_key, culture_key, period_key, available_profiles):
    current_profile_key = _to_profile_key(current_profile_key)
    culture_key = _to_profile_key(culture_key)
    period_key = _to_profile_key(period_key)
    available_profiles = tuple(available_profiles or [])
    base_state = {
        "recommended_profile_key": None,
        "comparison_base_key": None,
        "comparison_profile_key": None,
        "can_apply_recommended": False,
        "can_compare_recommended": False,
        "guidance_key": "recommended_profile_none",
        "guidance_default": "No saved local calibrated profile exists for this context yet.",
        "guidance_args": {},
    }

    if not current_profile_key:
        base_state.update(
            {
                "mode": "empty",
                "guidance_default": "No profile selected.",
            }
        )
        return base_state

    if not culture_key or not period_key:
        base_state.update(
            {
                "mode": "none",
                "guidance_default": "No saved local calibrated profile exists for this context yet.",
            }
        )
        return {
            **base_state,
            "mode": "none",
            "guidance_key": "recommended_profile_none",
            "guidance_default": "No saved local calibrated profile exists for this context yet.",
        }

    recommended_key = recommended_calibrated_profile(
        current_profile_key,
        culture_key or "",
        period_key or "",
        available_profiles,
    )
    if not recommended_key:
        comparison_base_key, comparison_profile_key = comparison_profile_pair(
            current_profile_key,
            culture_key,
            period_key,
            available_profiles,
        )
        if comparison_base_key and comparison_profile_key:
            return {
                **base_state,
                "mode": "compare_only",
                "comparison_base_key": comparison_base_key,
                "comparison_profile_key": comparison_profile_key,
                "can_compare_recommended": True,
                "guidance_key": "recommended_profile_compare_only",
                "guidance_default": "You can run a quick comparison between the calibrated profile and its base preset.",
            }
        return {
            **base_state,
            "mode": "none",
            "guidance_key": "recommended_profile_none",
            "guidance_default": "No saved local calibrated profile exists for this context yet.",
        }

    if recommended_key == current_profile_key:
        return {
            **base_state,
            "mode": "active",
            "recommended_profile_key": recommended_key,
            "guidance_key": "recommended_profile_active_template",
            "guidance_default": "Using the recommended calibrated profile: {profile}",
            "guidance_args": {"profile_key": recommended_key},
        }

    return {
        **base_state,
        "mode": "recommended",
        "recommended_profile_key": recommended_key,
        "comparison_base_key": current_profile_key,
        "comparison_profile_key": recommended_key,
        "can_apply_recommended": True,
        "can_compare_recommended": True,
        "guidance_key": "recommended_profile_hint_template",
        "guidance_default": "Recommended calibrated profile: {profile} ({key})",
        "guidance_args": {"key": recommended_key},
    }


def workflow_presentation_state(
    *,
    mode_name,
    action_name,
    checks,
    goal_name,
    profile_name,
    label_language,
    advanced_context_enabled,
    mountain_enabled,
    mountain_language,
    status_text,
):
    completed = sum(1 for _, done in checks if done)
    total = max(1, len(checks))
    percent = int(round((completed / total) * 100.0))
    lang_name = (
        ui_text("workflow_lang_ko", default="Korean")
        if label_language == "ko"
        else ui_text("workflow_lang_en", default="English")
    )
    context_mode = (
        ui_text("context_mode_general_short", default="General")
        if not advanced_context_enabled
        else ui_text("context_mode_advanced_short", default="Advanced")
    )
    mountain_mode = (
        ui_text("web_mountain_mode_on", default="On")
        if mountain_enabled
        else ui_text("web_mountain_mode_off", default="Off")
    )
    summary_text = ui_text(
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
        mountain_lang=mountain_language,
        percent=percent,
    )
    pending = next((label for label, done in checks if not done), None)
    if pending:
        next_step_text = ui_text(
            "workflow_next_template",
            default="Next step: {pending}",
        ).format(pending=pending)
    else:
        next_step_text = ui_text(
            "workflow_next_action_template",
            default="Next step: run with '{action}' button.",
        ).format(action=action_name)
    checklist_rows = []
    for label, done in checks:
        state = (
            ui_text("workflow_state_done", default="Done")
            if done
            else ui_text("workflow_state_pending", default="Pending")
        )
        color = "#1f6255" if done else "#8a6d3b"
        checklist_rows.append(
            f"<span style='color:{color};'><b>{state}</b></span> · {escape(label)}"
        )
    return {
        "percent": percent,
        "summary_text": summary_text,
        "next_step_text": next_step_text,
        "checklist_html": "<br/>".join(checklist_rows),
        "recent_status_text": ui_text(
            "workflow_recent_status_template",
            default="Recent status: {text}",
        ).format(text=status_text),
    }


def dem_diagnostics_state(
    *,
    layer_name=None,
    diagnostics=None,
    crs_is_geographic=False,
    error_text=None,
):
    if error_text:
        return {
            "html": ui_text(
                "guide_dem_diag_empty",
                default="<b>DEM Diagnostics</b><br/>Configuration error: {message}",
            ).format(message=escape(str(error_text))),
        }
    if not layer_name or not isinstance(diagnostics, dict):
        return {
            "html": ui_text(
                "guide_dem_diag_empty",
                default=(
                    "<b>DEM Diagnostics</b><br/>Select a DEM layer to inspect "
                    "resolution, CRS unit reliability, and sampling density."
                ),
            ),
        }
    crs_mode = "geographic" if crs_is_geographic else "projected"
    crs_note = (
        "distance/smoothing in degree units can distort interpretation"
        if crs_is_geographic
        else "distance/smoothing in projected units is more reliable"
    )
    return {
        "html": ui_text(
            "guide_dem_diag_template",
            default=(
                "<b>DEM Diagnostics</b><br/>"
                "layer={layer}<br/>"
                "pixel_step={step:.4f}, extent={width:.1f} x {height:.1f}, "
                "adaptive_spacing={spacing:.2f}, approx_sampling_nodes={nodes}<br/>"
                "CRS mode={crs_mode}: {crs_note}"
            ),
        ).format(
            layer=escape(layer_name),
            step=diagnostics.get("dem_step", 0.0),
            width=diagnostics.get("width", 0.0),
            height=diagnostics.get("height", 0.0),
            spacing=diagnostics.get("spacing", 0.0),
            nodes=diagnostics.get("approx_nodes", 0),
            crs_mode=crs_mode,
            crs_note=escape(crs_note),
        ),
    }


def evidence_summary_state(*, records, advanced_context_enabled, culture_key):
    if not advanced_context_enabled:
        return {
            "quality": "general_principles",
            "html": ui_text(
                "guide_evidence_general_mode",
                default=(
                    "<b>Evidence Summary</b><br/>"
                    "General principles mode: region/period evidence is intentionally not applied."
                ),
            ),
        }
    if not isinstance(records, list) or not records:
        return {
            "quality": "empty",
            "html": ui_text(
                "guide_evidence_empty",
                default="<b>Evidence Summary</b><br/>No context evidence loaded.",
            ),
        }
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
    if culture_visibility_tier(culture_key) == "experimental":
        if quality not in ("Exploratory", "Moderate"):
            quality = "Exploratory"
        quality += " (experimental region profile)"
    recommendation = (
        "Includes many heuristic priors (C/U); run calibration and local validation."
        if low_count > 0
        else "Mostly A/B evidence for this context."
    )
    return {
        "quality": quality,
        "counts": counts,
        "html": ui_text(
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
        ),
    }


def context_evidence_state(
    *,
    advanced_context_enabled,
    culture_key,
    culture_name,
    period_name,
    ui_language,
    records,
    selected_index,
):
    if not advanced_context_enabled:
        return {
            "records": [],
            "combo_items": [],
            "selected_index": -1,
            "hint_text": ui_text(
                "context_general_mode_hint",
                default=(
                    "General principles mode is active. Country/period biases are disabled. "
                    "Enable advanced context to apply regional and historical profiles."
                ),
            ),
            "param_hint_text": ui_text(
                "context_general_mode_note",
                default="Using neutral global principles only (no country/period overrides).",
            ),
        }

    records = list(records or [])
    decorated_culture_name = culture_name
    if culture_visibility_tier(culture_key) == "experimental":
        suffix = " (실험적)" if ui_language == "ko" else " (Exploratory)"
        if suffix not in decorated_culture_name:
            decorated_culture_name = f"{decorated_culture_name}{suffix}"

    combo_items = []
    for index, item in enumerate(records):
        combo_items.append(
            {
                "label": f"{item.get('group', '-')}.{item.get('name', '-')}",
                "data": index,
            }
        )

    source_list = []
    for item in records:
        for source in item.get("source_doi", []):
            if source not in source_list:
                source_list.append(source)
        if len(source_list) >= 2:
            break

    hint_text = ui_text(
        "context_hint_template",
        default="Profile evidence: {culture} / {period} (details: '{button}').",
    ).format(
        culture=decorated_culture_name,
        period=period_name,
        button=ui_text("context_evidence_button", default="View Context Evidence"),
    )
    references_text = reference_display_text(
        source_list,
        language=ui_language,
        limit=2,
    )
    if references_text:
        hint_text += ui_text(
            "context_hint_reference_prefix",
            default=" Representative references: ",
        )
        hint_text += references_text

    if not records:
        return {
            "records": records,
            "combo_items": combo_items,
            "selected_index": -1,
            "hint_text": hint_text,
            "param_hint_text": ui_text(
                "context_no_params",
                default="No parameter evidence.",
            ),
        }

    if not isinstance(selected_index, int) or selected_index < 0 or selected_index >= len(records):
        selected_index = 0
    item = records[selected_index]
    value = item.get("value")
    if isinstance(value, float):
        value_text = f"{value:.4f}".rstrip("0").rstrip(".")
    else:
        value_text = str(value)
    references_text = reference_display_text(
        item.get("source_doi", []),
        language=ui_language,
    )
    if not references_text:
        references_text = ui_text(
            "context_no_reference",
            default="No reference",
        )
    note = item.get("note") or ui_text("context_no_note", default="No note")
    param_hint_text = ui_text(
        "context_param_reference_template",
        default=(
            "[{group}.{name}] value={value} | evidence={level} | "
            "reference={reference} | note={note}"
        ),
    ).format(
        group=item.get("group", "-"),
        name=item.get("name", "-"),
        value=value_text,
        level=item.get("evidence_level", "U"),
        reference=references_text,
        note=note,
    )
    return {
        "records": records,
        "combo_items": combo_items,
        "selected_index": selected_index,
        "hint_text": hint_text,
        "param_hint_text": param_hint_text,
    }
