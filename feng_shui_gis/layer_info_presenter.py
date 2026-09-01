# -*- coding: utf-8 -*-
"""Layer alias / display / maptip presentation helpers."""

from __future__ import annotations


def _display_field(field_names, label_lang, *, generalized, korean, english, fallback):
    """Pick the label column that actually carries the requested language.

    Layers written before the generalized ``*_lbl`` columns existed only carry
    Korean and English, so those stay the fallback rather than exposing raw ids.
    """
    if label_lang == "ko":
        return korean if korean in field_names else fallback
    if generalized in field_names:
        return generalized
    if label_lang == "en" and english in field_names:
        return english
    return korean if korean in field_names else fallback


def mountain_tip_html(field_names, *, maptip_mountain, maptip_mountain_dist, maptip_mountain_lang):
    if "mt_name" not in field_names:
        return ""
    return (
        f"<p><b>{maptip_mountain}</b>: [% coalesce(\"mt_name\", 'n/a') %], "
        f"<b>{maptip_mountain_dist}</b>: "
        "[% CASE WHEN \"mt_dist_m\" IS NULL THEN 'n/a' ELSE to_string(round(\"mt_dist_m\", 1)) END %], "
        f"<b>{maptip_mountain_lang}</b>: [% coalesce(\"mt_lang\", 'n/a') %]</p>"
    )


def link_layer_info_config(
    field_names,
    *,
    label_lang,
    link_arrow,
    reason_label,
    reason_empty_lit,
    mountain_tip,
    link_alias_score,
    link_alias_len_m,
    link_alias_azimuth,
    link_alias_rank,
    maptip_score,
    maptip_len_m,
    maptip_azimuth,
    maptip_link_note,
    score_band_expr,
):
    if not {"src_id", "dst_id"} <= field_names:
        return None
    term_field = _display_field(
        field_names,
        label_lang,
        generalized="term_lbl",
        korean="term_ko",
        english="term_en",
        fallback="term_id",
    )
    src_field = _display_field(
        field_names,
        label_lang,
        generalized="src_lbl",
        korean="src_ko",
        english="src_en",
        fallback="src_id",
    )
    dst_field = _display_field(
        field_names,
        label_lang,
        generalized="dst_lbl",
        korean="dst_ko",
        english="dst_en",
        fallback="dst_id",
    )
    return {
        "aliases": {
            "score": link_alias_score,
            "len_m": link_alias_len_m,
            "azimuth": link_alias_azimuth,
            "rank": link_alias_rank,
        },
        "display_expression": f"\"{term_field}\" || ' ' || \"{src_field}\" || ' {link_arrow} ' || \"{dst_field}\"",
        "map_tip_template": (
            f"<h3>[% \"{term_field}\" %] [% \"{src_field}\" %] {link_arrow} [% \"{dst_field}\" %]</h3>"
            f"<p><b>{reason_label}</b>: [% coalesce(\"reason_ko\",'{reason_empty_lit}') %]</p>"
            f"<p><b>{maptip_score}</b>: [% round(\"score\", 3) %] ([% {score_band_expr} %]), "
            f"<b>{maptip_len_m}</b>: [% round(\"len_m\", 1) %], "
            f"<b>{maptip_azimuth}</b>: [% round(\"azimuth\", 1) %]</p>"
            f"{mountain_tip}"
            f"<p><small>{maptip_link_note}</small></p>"
        ),
        "reason_field": "reason_ko",
    }


def term_layer_info_config(
    field_names,
    *,
    label_lang,
    reason_label,
    reason_empty_lit,
    mountain_tip,
    term_alias_score,
    term_alias_fit,
    term_alias_delta,
    term_alias_target,
    term_alias_radius,
    term_alias_relief,
    term_alias_rank,
    maptip_score,
    maptip_rank,
    maptip_fit,
    maptip_delta,
    maptip_target,
    maptip_radius_m,
    maptip_term_note,
    score_band_expr,
):
    if "term_ko" not in field_names:
        return None
    # term_name already carries the label in whichever language the run selected.
    term_field = (
        "term_name" if label_lang != "ko" and "term_name" in field_names else "term_ko"
    )
    if "fit_sc" in field_names:
        map_tip_template = (
            f"<h3>[% \"{term_field}\" %]</h3>"
            f"<p><b>{reason_label}</b>: [% coalesce(\"reason_ko\",'{reason_empty_lit}') %]</p>"
            f"<p><b>{maptip_score}</b>: [% round(\"score\", 3) %] ([% {score_band_expr} %]), "
            f"<b>{maptip_rank}</b>: [% \"rank\" %], "
            f"<b>{maptip_fit}</b>: [% round(\"fit_sc\", 3) %]</p>"
            f"<p><b>{maptip_delta}</b>: [% round(\"delta_rel\", 4) %], "
            f"<b>{maptip_target}</b>: [% round(\"target_rel\", 4) %], "
            f"<b>{maptip_radius_m}</b>: [% round(\"radius_m\", 1) %]</p>"
            f"{mountain_tip}"
            f"<p><small>{maptip_term_note}</small></p>"
        )
    else:
        map_tip_template = (
            f"<h3>[% \"{term_field}\" %]</h3>"
            f"<p><b>{reason_label}</b>: [% coalesce(\"reason_ko\",'{reason_empty_lit}') %]</p>"
            f"<p><b>{maptip_score}</b>: [% round(\"score\", 3) %] ([% {score_band_expr} %]), "
            f"<b>{maptip_rank}</b>: [% \"rank\" %]</p>"
            f"{mountain_tip}"
        )
    return {
        "aliases": {
            "score": term_alias_score,
            "fit_sc": term_alias_fit,
            "delta_rel": term_alias_delta,
            "target_rel": term_alias_target,
            "radius_m": term_alias_radius,
            "relief_m": term_alias_relief,
            "rank": term_alias_rank,
        },
        "display_expression": f"\"{term_field}\"",
        "map_tip_template": map_tip_template,
        "reason_field": "reason_ko",
    }


def ridge_layer_info_config(
    field_names,
    *,
    label_lang,
    reason_label,
    reason_empty_lit,
    mountain_tip,
    ridge_alias_strength,
    ridge_alias_score,
    ridge_alias_len,
    maptip_strength,
    maptip_ridge_score,
    maptip_len,
    maptip_ridge_note,
):
    if "ridge_class" not in field_names:
        return None
    ridge_label_field = "ridge_ko" if "ridge_ko" in field_names else "ridge_class"
    if label_lang == "en" and "ridge_en" in field_names:
        ridge_label_field = "ridge_en"
    return {
        "aliases": {
            "strength": ridge_alias_strength,
            "ridge_score": ridge_alias_score,
            "len": ridge_alias_len,
        },
        "display_expression": f"\"{ridge_label_field}\" || ' #' || \"ridge_rank\"",
        "map_tip_template": (
            f"<h3>[% \"{ridge_label_field}\" %] / #% \"ridge_rank\"</h3>"
            f"<p><b>{reason_label}</b>: [% coalesce(\"reason_ko\",'{reason_empty_lit}') %]</p>"
            f"<p><b>{maptip_strength}</b>: [% round(\"strength\", 3) %], "
            f"<b>{maptip_ridge_score}</b>: [% round(\"ridge_score\", 3) %], "
            f"<b>{maptip_len}</b>: [% round(\"len\", 1) %]</p>"
            f"{mountain_tip}"
            f"<p><small>{maptip_ridge_note}</small></p>"
        ),
        "reason_field": "reason_ko",
    }


def stream_layer_info_config(
    field_names,
    *,
    reason_label,
    reason_empty_lit,
    mountain_tip,
    hydro_alias_order,
    hydro_alias_flow_acc,
    hydro_alias_len,
    maptip_order,
    maptip_flow_acc,
    maptip_len,
    maptip_hydro_note,
):
    if "stream_class" not in field_names:
        return None
    return {
        "aliases": {
            "order": hydro_alias_order,
            "flow_acc": hydro_alias_flow_acc,
            "len": hydro_alias_len,
        },
        "display_expression": "\"stream_class\" || ' #' || \"stream_id\"",
        "map_tip_template": (
            "<h3>[% \"stream_class\" %] / #% \"stream_id\"</h3>"
            f"<p><b>{reason_label}</b>: [% coalesce(\"reason_ko\",'{reason_empty_lit}') %]</p>"
            f"<p><b>{maptip_order}</b>: [% \"order\" %], "
            f"<b>{maptip_flow_acc}</b>: [% round(\"flow_acc\", 2) %], "
            f"<b>{maptip_len}</b>: [% round(\"len\", 1) %]</p>"
            f"{mountain_tip}"
            f"<p><small>{maptip_hydro_note}</small></p>"
        ),
        "reason_field": "reason_ko",
    }


def compare_layer_info_config(
    field_names,
    *,
    reason_empty_lit,
    mountain_tip,
    compare_change_feature_alias,
    compare_change_base_alias,
    compare_change_calibrated_alias,
    compare_change_delta_alias,
    compare_change_trend_alias,
    compare_change_reason_b_alias,
    compare_change_reason_c_alias,
    compare_change_model_alias,
    compare_change_gain_label,
    compare_change_drop_label,
    compare_change_neutral_label,
):
    required = {
        "cmp_label",
        "cmp_base",
        "cmp_score",
        "cmp_delta",
        "cmp_trend",
        "cmp_reason_b",
        "cmp_reason_c",
        "cmp_model",
    }
    if not required <= field_names:
        return None
    compare_change_trend_expr = (
        f"CASE WHEN \"cmp_trend\" = 'gain' THEN '{compare_change_gain_label}' "
        f"WHEN \"cmp_trend\" = 'drop' THEN '{compare_change_drop_label}' "
        f"ELSE '{compare_change_neutral_label}' END"
    )
    return {
        "aliases": {
            "cmp_label": compare_change_feature_alias,
            "cmp_base": compare_change_base_alias,
            "cmp_score": compare_change_calibrated_alias,
            "cmp_delta": compare_change_delta_alias,
            "cmp_trend": compare_change_trend_alias,
            "cmp_reason_b": compare_change_reason_b_alias,
            "cmp_reason_c": compare_change_reason_c_alias,
            "cmp_model": compare_change_model_alias,
        },
        "display_expression": "\"cmp_label\"",
        "map_tip_template": (
            f"<h3>[% \"cmp_label\" %]</h3>"
            f"<p><b>{compare_change_base_alias}</b>: [% round(\"cmp_base\", 3) %], "
            f"<b>{compare_change_calibrated_alias}</b>: [% round(\"cmp_score\", 3) %], "
            f"<b>{compare_change_delta_alias}</b>: [% round(\"cmp_delta\", 3) %], "
            f"<b>{compare_change_trend_alias}</b>: [% {compare_change_trend_expr} %]</p>"
            f"<p><b>{compare_change_model_alias}</b>: [% coalesce(\"cmp_model\", 'n/a') %]</p>"
            f"<p><b>{compare_change_reason_b_alias}</b>: [% coalesce(\"cmp_reason_b\",'{reason_empty_lit}') %]</p>"
            f"<p><b>{compare_change_reason_c_alias}</b>: [% coalesce(\"cmp_reason_c\",'{reason_empty_lit}') %]</p>"
            f"{mountain_tip}"
        ),
        "reason_field": "fs_reason",
    }


def site_layer_info_config(
    field_names,
    *,
    reason_label,
    reason_empty_lit,
    mountain_tip,
    fs_score_title,
    cal_score_title,
    site_alias_score,
    site_alias_conf,
    site_alias_slope,
    site_alias_aspect,
    site_alias_form,
    site_alias_long,
    site_alias_water,
    site_alias_dem_water,
    site_alias_tpi,
    site_alias_conv,
    cal_score_alias,
    cal_f1_alias,
    cal_youden_alias,
    maptip_score,
    maptip_coverage,
    maptip_components,
    maptip_terrain,
    maptip_dem_water,
    maptip_distance_water,
    maptip_site_note,
    maptip_base_fs_score,
    maptip_best_f1_th,
    maptip_best_youden_th,
    site_score_band_expr,
    site_alias_missing,
    maptip_missing,
):
    if "fs_reason" not in field_names:
        return None
    score_field = "cal_score" if "cal_score" in field_names else "fs_score"
    score_title = cal_score_title if score_field == "cal_score" else fs_score_title
    threshold_tip = ""
    if "cal_score" in field_names:
        threshold_tip = (
            f"<p><b>{maptip_base_fs_score}</b>: [% round(\"fs_score\", 3) %]"
            + (
                f", <b>{maptip_best_f1_th}</b>: [% round(\"cal_f1_th\", 3) %]"
                if "cal_f1_th" in field_names
                else ""
            )
            + (
                f", <b>{maptip_best_youden_th}</b>: [% round(\"cal_yj_th\", 3) %]"
                if "cal_yj_th" in field_names
                else ""
            )
            + "</p>"
        )
    missing_tip = ""
    if "fs_missing" in field_names:
        missing_tip = (
            f"<p>[% CASE WHEN coalesce(\"fs_missing\",'') = '' THEN '' "
            f"ELSE '<b>{maptip_missing}</b>: ' || \"fs_missing\" END %]</p>"
        )
    return {
        "aliases": {
            "fs_score": site_alias_score,
            "fs_cover": site_alias_conf,
            "fs_missing": site_alias_missing,
            "fs_slope": site_alias_slope,
            "fs_aspect": site_alias_aspect,
            "fs_form": site_alias_form,
            "fs_long": site_alias_long,
            "fs_water": site_alias_water,
            "fs_demwtr": site_alias_dem_water,
            "fs_tpi": site_alias_tpi,
            "fs_conv": site_alias_conv,
            "cal_score": cal_score_alias,
            "cal_f1_th": cal_f1_alias,
            "cal_yj_th": cal_youden_alias,
        },
        "display_expression": f"'{score_field}=' || to_string(round(\"{score_field}\", 3))",
        "map_tip_template": (
            f"<h3>{score_title}</h3>"
            f"<p><b>{maptip_score}</b>: [% round(\"{score_field}\", 3) %] ([% {site_score_band_expr} %]), "
            # Coverage is a completeness fraction, so it gets no strong/weak
            # band - those bands belong to the score alone.
            f"<b>{maptip_coverage}</b>: [% round(\"fs_cover\", 2) %]</p>"
            f"{missing_tip}"
            f"{threshold_tip}"
            f"<p><b>{maptip_components}</b>: "
            "slope=[% round(\"fs_slope\", 3) %], "
            "aspect=[% round(\"fs_aspect\", 3) %], "
            "form=[% round(\"fs_form\", 3) %], "
            "long=[% round(\"fs_long\", 3) %], "
            "water=[% round(\"fs_water\", 3) %]</p>"
            f"<p><b>{maptip_terrain}</b>: "
            "TPI=[% round(\"fs_tpi\", 4) %], "
            "convergence=[% round(\"fs_conv\", 3) %], "
            f"{maptip_dem_water}=[% round(\"fs_demwtr\", 3) %], "
            f"{maptip_distance_water}=[% round(\"fs_water_m\", 1) %]</p>"
            f"{mountain_tip}"
            f"<p><small>{maptip_site_note}</small></p>"
            f"<p><b>{reason_label}</b>: [% coalesce(\"fs_reason\",'{reason_empty_lit}') %]</p>"
        ),
        "reason_field": "fs_reason",
    }
