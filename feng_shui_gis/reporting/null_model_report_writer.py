"""Adapter layer for background-comparison (null model) report output.

A comparison that lives only in a session cannot be cited, and one whose
numbers travel without their background policy cannot be reproduced. This
writer keeps the two together: the policy, the seed, and the claim limits sit
in the same payload as the effect size, and the Markdown leads with them
rather than burying them under the result.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _sampling_record(sample: Dict[str, Any] | None) -> Dict[str, Any]:
    sample = sample or {}
    rejected = sample.get("rejected") or {}
    drawn = len(sample.get("scores") or [])
    requested = int(sample.get("requested", 0) or 0)
    return {
        "requested": requested,
        "drawn": drawn,
        "complete": bool(sample.get("complete", False)),
        "attempts": int(sample.get("attempts", 0) or 0),
        "attempt_cap": int(sample.get("attempt_cap", 0) or 0),
        "rejected": {str(key): int(value) for key, value in rejected.items()},
        "shortfall": max(0, requested - drawn),
    }


class NullModelReportWriter:
    """Keep background-comparison output schema aligned across UI and scripts."""

    @staticmethod
    def payload(
        *,
        stamp: str,
        site_layer_name: str,
        comparison: Dict[str, Any],
        sample: Dict[str, Any] | None = None,
        profile_key: str = "",
        culture_key: str = "",
        period_key: str = "",
        scoring_note: str = "",
        dem_layer_name: str = "",
    ) -> Dict[str, Any]:
        comparison = comparison or {}
        usable = bool(comparison.get("usable"))
        permutation = comparison.get("permutation") or {}
        sampling = _sampling_record(sample)

        interpretation = {
            "question": (
                "Do the observed sites occupy terrain this model scores "
                "differently from background positions in the same landscape?"
            ),
            "site_layer": site_layer_name,
            "dem_layer": dem_layer_name,
            "profile": profile_key,
            "culture": culture_key,
            "period": period_key,
            # The policy is what fixes the meaning of the result, so it is
            # interpretation, not a footnote in the statistics.
            "background_policy": str(comparison.get("background_policy", "")),
            "establishes": str(comparison.get("establishes", "")),
            "does_not_establish": str(comparison.get("does_not_establish", "")),
            "scoring_note": scoring_note,
            "usable": usable,
        }

        if usable:
            analytical: Dict[str, Any] = {
                "n_observed": int(comparison.get("n_observed", 0)),
                "n_background": int(comparison.get("n_background", 0)),
                "observed_mean": _to_float(comparison.get("observed_mean")),
                "background_mean": _to_float(comparison.get("background_mean")),
                "observed_median": _to_float(comparison.get("observed_median")),
                "background_median": _to_float(comparison.get("background_median")),
                "mean_percentile": _to_float(comparison.get("mean_percentile")),
                "cliffs_delta": _to_float(comparison.get("cliffs_delta")),
                "effect_magnitude": str(comparison.get("effect_magnitude", "")),
                "p_value": _to_float(permutation.get("p_value")),
                "observed_difference": _to_float(permutation.get("observed_difference")),
                "alternative": str(permutation.get("alternative", "")),
            }
        else:
            analytical = {
                "reason": str(comparison.get("reason", "unusable")),
                "n_observed": int(comparison.get("n_observed", 0)),
                "n_background": int(comparison.get("n_background", 0)),
            }
        analytical["sampling"] = sampling

        audit = {
            "seed": int(permutation.get("seed", 0) or 0),
            "iterations": int(permutation.get("iterations", 0) or 0),
            "background_sample_complete": sampling["complete"],
            "background_shortfall": sampling["shortfall"],
            # Effect size decides whether there is anything to say; a small
            # p-value on a negligible delta is a large sample, not a finding.
            "effect_reportable": bool(
                usable and str(comparison.get("effect_magnitude", "")) != "negligible"
            ),
        }
        return {
            "timestamp": stamp,
            "interpretation": interpretation,
            "analytical": analytical,
            "audit": audit,
        }

    @staticmethod
    def build_markdown(
        *,
        stamp: str,
        site_layer_name: str,
        comparison: Dict[str, Any],
        sample: Dict[str, Any] | None = None,
        profile_key: str = "",
        culture_key: str = "",
        period_key: str = "",
        scoring_note: str = "",
        dem_layer_name: str = "",
    ) -> str:
        payload = NullModelReportWriter.payload(
            stamp=stamp,
            site_layer_name=site_layer_name,
            comparison=comparison,
            sample=sample,
            profile_key=profile_key,
            culture_key=culture_key,
            period_key=period_key,
            scoring_note=scoring_note,
            dem_layer_name=dem_layer_name,
        )
        interpretation = payload["interpretation"]
        analytical = payload["analytical"]
        audit = payload["audit"]
        sampling = analytical["sampling"]

        lines = [
            f"# Background Comparison Report ({stamp})",
            "",
            "## Interpretation",
            f"- question: {interpretation['question']}",
            f"- site layer: {site_layer_name}",
            f"- dem layer: {dem_layer_name or 'n/a'}",
            f"- profile: {profile_key or 'n/a'}",
            f"- context: {culture_key or 'n/a'} / {period_key or 'n/a'}",
            f"- background policy: {interpretation['background_policy'] or 'n/a'}",
        ]
        if scoring_note:
            lines.append(f"- scoring: {scoring_note}")
        lines += [
            "",
            "### What this establishes",
            f"- {interpretation['establishes'] or 'n/a'}",
            "",
            "### What this does not establish",
            f"- {interpretation['does_not_establish'] or 'n/a'}",
            "",
            "## Analytical",
        ]

        if not interpretation["usable"]:
            lines += [
                f"- result: not usable ({analytical.get('reason', 'unusable')})",
                f"- observed n: {analytical['n_observed']}",
                f"- background n: {analytical['n_background']}",
            ]
        else:
            lines += [
                f"- observed n: {analytical['n_observed']}, "
                f"background n: {analytical['n_background']}",
                f"- observed mean: {analytical['observed_mean']:.4f} "
                f"(median {analytical['observed_median']:.4f})",
                f"- background mean: {analytical['background_mean']:.4f} "
                f"(median {analytical['background_median']:.4f})",
                f"- mean percentile of observed within background: "
                f"{analytical['mean_percentile']:.3f}",
                f"- Cliff's delta: {analytical['cliffs_delta']:+.4f} "
                f"({analytical['effect_magnitude']})",
                f"- permutation p ({analytical['alternative']}): "
                f"{analytical['p_value']:.4f}",
            ]
            if not audit["effect_reportable"]:
                lines.append(
                    "- NOTE: effect magnitude is negligible; a small p-value here "
                    "reflects sample size, not a difference worth reporting."
                )

        lines += [
            "",
            "### Background sampling",
            f"- requested: {sampling['requested']}, drawn: {sampling['drawn']}",
            f"- attempts: {sampling['attempts']} (cap {sampling['attempt_cap']})",
        ]
        if sampling["rejected"]:
            rejected = ", ".join(
                f"{key}={value}" for key, value in sorted(sampling["rejected"].items())
            )
            lines.append(f"- rejected: {rejected}")
        if not sampling["complete"]:
            lines.append(
                f"- WARNING: background sample fell short by {sampling['shortfall']}; "
                "the background drawn is not the background requested."
            )

        lines += [
            "",
            "## Audit",
            f"- seed: {audit['seed']}",
            f"- permutation iterations: {audit['iterations']}",
            f"- background sample complete: {audit['background_sample_complete']}",
            f"- effect reportable: {audit['effect_reportable']}",
        ]
        return "\n".join(lines)

def write_null_model_report_files(
    *,
    report_dir: str,
    stamp: str,
    site_layer_name: str,
    comparison: Dict[str, Any],
    sample: Dict[str, Any] | None = None,
    profile_key: str = "",
    culture_key: str = "",
    period_key: str = "",
    scoring_note: str = "",
    dem_layer_name: str = "",
) -> Dict[str, str]:
    """Write the JSON and Markdown pair, matching the other report writers."""
    base_name = f"feng_shui_background_{stamp}"
    json_path = os.path.join(report_dir, f"{base_name}.json")
    md_path = os.path.join(report_dir, f"{base_name}.md")
    common = {
        "stamp": stamp,
        "site_layer_name": site_layer_name,
        "comparison": comparison,
        "sample": sample,
        "profile_key": profile_key,
        "culture_key": culture_key,
        "period_key": period_key,
        "scoring_note": scoring_note,
        "dem_layer_name": dem_layer_name,
    }
    payload = NullModelReportWriter.payload(**common)
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as handle:
        handle.write(NullModelReportWriter.build_markdown(**common))
    return {"json_path": json_path, "md_path": md_path}

