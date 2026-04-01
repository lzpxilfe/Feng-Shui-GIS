# -*- coding: utf-8 -*-
"""State helpers for usage-goal / advanced-panel UI policy."""

from __future__ import annotations

from html import escape


def advanced_options_panel_state(expanded):
    expanded = bool(expanded)
    return {
        "expanded": expanded,
        "panel_visible": expanded,
        "button_checked": expanded,
        "arrow": "down" if expanded else "right",
    }


def usage_goal_preset_state(goal_key, *, profile_key=None, include_terms=False):
    return {
        "profile_key": profile_key or "",
        "include_terms": bool(include_terms),
        "force_analysis_tab": bool(profile_key),
        "expand_advanced": goal_key == "custom",
    }


def usage_goal_guidance_state(
    goal_key,
    *,
    goal_label,
    profile_label_text,
    custom_hint_template,
    default_hint_template,
    guide_intro_html,
    guide_steps_html,
):
    if goal_key == "custom":
        goal_hint_html = custom_hint_template.format(
            profile=escape(profile_label_text or "")
        )
    else:
        goal_hint_html = default_hint_template.format(
            goal=escape(goal_label),
            profile=escape(profile_label_text or ""),
        )
    return {
        "goal_hint_html": goal_hint_html,
        "guide_intro_html": guide_intro_html,
        "guide_steps_html": guide_steps_html,
    }
