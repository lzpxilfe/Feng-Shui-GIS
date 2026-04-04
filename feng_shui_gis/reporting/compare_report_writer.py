"""Adapter layer for compare report payload and renderers."""

from __future__ import annotations

from typing import Any, Dict, List


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _top_change_rows(top_changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for row in top_changes or []:
        if not isinstance(row, dict):
            continue
        base = _to_float(row.get("base_score", 0.0))
        compare = _to_float(row.get("compare_score", 0.0))
        rows.append(
            {
                "feature_uid": str(row.get("feature_uid", "")).strip(),
                "label": str(row.get("label", "n/a")),
                "base_score": base,
                "compare_score": compare,
                "delta": _to_float(row.get("delta", compare - base)),
                "base_reason": str(row.get("base_reason", "")),
                "compare_reason": str(row.get("compare_reason", "")),
            }
        )
    return rows


class CompareReportWriter:
    """Keep compare report output schema aligned across UI, file, and smoke scripts."""

    @staticmethod
    def payload(
        *,
        stamp: str,
        site_layer_name: str,
        base_profile_key: str,
        compare_profile_key: str,
        base_stats: Dict[str, Any],
        compare_stats: Dict[str, Any],
        delta_stats: Dict[str, Any],
        top_changes: List[Dict[str, Any]],
        change_layer_name: str,
        reason_excerpt_limit: int = 88,
        trust_metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        normalized = _top_change_rows(top_changes)
        interpretation = {
            "selected_profiles": {
                "base": base_profile_key,
                "compare": compare_profile_key,
            },
            "site_layer": site_layer_name,
            "change_layer": change_layer_name,
            "trust_metadata": trust_metadata or {},
            "focus": "gain_drop relative to selected profile",
        }
        analytical = {
            "base_stats": dict(base_stats or {}),
            "compare_stats": dict(compare_stats or {}),
            "delta_stats": dict(delta_stats or {}),
            "top_changes": normalized,
            "top_change_count": len(normalized),
            "reason_excerpt_limit": int(reason_excerpt_limit),
        }
        audit = {
            "top_change_feature_uids": [row["feature_uid"] for row in normalized if row["feature_uid"]],
            "result_badges": (trust_metadata or {}).get("result_badges", []),
            "compare_notice": (trust_metadata or {}).get("compare_notice", ""),
            "score_notice": (trust_metadata or {}).get("score_notice", ""),
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
        text_lang: str,
        site_layer_name: str,
        base_profile_key: str,
        compare_profile_key: str,
        base_stats: Dict[str, Any],
        compare_stats: Dict[str, Any],
        delta_stats: Dict[str, Any],
        top_changes: List[Dict[str, Any]],
        change_layer_name: str,
        reason_excerpt_limit: int = 44,
        trust_metadata: Dict[str, Any] | None = None,
    ) -> str:
        del text_lang
        del reason_excerpt_limit
        normalized = _top_change_rows(top_changes)
        header = f"# Feng Shui Comparison Report ({stamp})"
        interpretation = [
            "## Interpretation",
            "- compare means gain/drop relative to selected base profile",
            f"- base profile: {base_profile_key}",
            f"- compare profile: {compare_profile_key}",
            f"- site layer: {site_layer_name}",
            f"- change layer: {change_layer_name}",
        ]
        analytical = [
            "## Analytical",
            "### Summary statistics",
            f"- base mean: {_to_float(base_stats.get('mean', 0.0), 0):.4f}",
            f"- compare mean: {_to_float(compare_stats.get('mean', 0.0), 0):.4f}",
            f"- mean delta: {_to_float(delta_stats.get('mean_delta', 0.0), 0):+.4f}",
            f"- max gain: {_to_float(delta_stats.get('max_gain', 0.0), 0):+.4f}",
            f"- max drop: {_to_float(delta_stats.get('max_drop', 0.0), 0):+.4f}",
            "",
            "### Top changed features",
        ]
        for row in normalized:
            analytical.append(
                "- {label}: {base_score:.4f} -> {compare_score:.4f} ({delta:+.4f})".format(
                    label=row["label"],
                    base_score=row["base_score"],
                    compare_score=row["compare_score"],
                    delta=row["delta"],
                )
            )
        if not normalized:
            analytical.append("- no top changes recorded")
        if trust_metadata:
            analytical.append("")
            analytical.append(
                f"- result badges: {', '.join((trust_metadata.get('result_badges') or []))}"
            )
        audit = [
            "## Audit",
            f"- top changed feature uids: {[row['feature_uid'] for row in normalized]}",
            f"- compare_notice: {str((trust_metadata or {}).get('compare_notice', ''))}",
        ]
        return "\n".join([header, ""] + interpretation + [""] + analytical + [""] + audit)

    @staticmethod
    def build_popup_html(
        *,
        text_lang: str,
        base_profile_key: str,
        compare_profile_key: str,
        base_stats: Dict[str, Any],
        compare_stats: Dict[str, Any],
        delta_stats: Dict[str, Any],
        top_changes: List[Dict[str, Any]],
        selected_change_count: int,
        zoom_applied: bool,
        change_layer_name: str,
        json_path: str,
        md_path: str,
        base_layer_name: str,
        compare_layer_name: str,
        reason_excerpt_limit: int = 88,
        trust_metadata: Dict[str, Any] | None = None,
    ) -> str:
        del text_lang
        del reason_excerpt_limit
        rows = _top_change_rows(top_changes)
        selected_note = (
            f"<p><b>Auto-selected:</b> selected {selected_change_count} top changed features on the map.</p>"
            if selected_change_count > 0
            else "<p>No top changes were auto-selected.</p>"
        )
        zoom_note = (
            "<p><b>Auto-zoom:</b> moved to selected calibrated features.</p>"
            if zoom_applied
            else ""
        )
        lines = [
            f"<h3>Interpretation</h3>",
            f"<p>Compare gain/drop is interpreted relative to {base_profile_key}.</p>",
            f"<h3>Analytical</h3>",
            f"<p><b>Base</b>: {base_layer_name} / <b>Calibrated</b>: {compare_layer_name}</p>",
            f"<p><b>Base mean</b>: {_to_float(base_stats.get('mean', 0.0), 0):.4f} "
            f"<b>Cal mean</b>: {_to_float(compare_stats.get('mean', 0.0), 0):.4f}</p>",
            f"<p><b>Mean delta</b>: {_to_float(delta_stats.get('mean_delta', 0.0), 0):+.4f}</p>",
            selected_note,
            zoom_note,
            f"<p><b>Compare JSON</b>: {json_path}<br/><b>Compare Markdown</b>: {md_path}</p>",
            f"<p><b>Change layer</b>: {change_layer_name}</p>",
            "<h3>Top changes</h3>",
        ]
        for row in rows:
            lines.append(
                f"<p><b>{row['label']}</b>: {row['base_score']:.4f} -> {row['compare_score']:.4f} "
                f"({row['delta']:+.4f})</p>"
            )
            if row["base_reason"]:
                lines.append(f"<p style='font-size:11px'><b>Base:</b> {row['base_reason']}</p>")
            if row["compare_reason"]:
                lines.append(f"<p style='font-size:11px'><b>Cal:</b> {row['compare_reason']}</p>")
        if not rows:
            lines.append("<p>No top changes were computed.</p>")

        audit = [
            "<h3>Audit</h3>",
            f"<p><b>Audit UIDs:</b> {', '.join(row['feature_uid'] for row in rows if row['feature_uid']) or 'none'}</p>",
            f"<p><b>Result badges:</b> {', '.join((trust_metadata or {}).get('result_badges', []) )}</p>",
        ]
        lines.extend(audit)
        return "\n".join(lines)
