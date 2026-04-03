# -*- coding: utf-8 -*-
from __future__ import annotations


def advanced_context_control_state(enabled):
    return {
        "culture_combo_enabled": bool(enabled),
        "period_combo_enabled": bool(enabled),
        "context_param_combo_enabled": bool(enabled),
        "show_experimental_contexts_enabled": bool(enabled),
    }


def mountain_control_state(enabled):
    return {
        "language_enabled": bool(enabled),
        "radius_enabled": bool(enabled),
        "limit_enabled": bool(enabled),
    }
