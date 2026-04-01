# -*- coding: utf-8 -*-
"""View-model helpers for dock-widget decision state."""

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from .cultural_context import neutral_context_key


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
