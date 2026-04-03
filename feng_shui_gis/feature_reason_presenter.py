# -*- coding: utf-8 -*-
"""Feature-reason message and popup HTML helpers."""

from __future__ import annotations

from html import escape


def _field_names(feature):
    try:
        return feature.fields().names()
    except Exception:
        return []


def build_feature_reason_message(
    feature,
    reason_field,
    *,
    reason_empty,
    mountain_prefix,
    mountain_lang_label,
):
    field_names = _field_names(feature)
    value = feature[reason_field] if reason_field in field_names else None
    message = str(value).strip() if value not in (None, "") else reason_empty
    if "mt_name" not in field_names:
        return message

    mountain_name = feature["mt_name"]
    if mountain_name in (None, ""):
        return message

    dist_text = ""
    if "mt_dist_m" in field_names:
        try:
            dist_text = f" ({float(feature['mt_dist_m']):.1f}m)"
        except (TypeError, ValueError):
            dist_text = ""

    source_text = ""
    if "mt_source" in field_names and feature["mt_source"] not in (None, ""):
        source_text = f", {feature['mt_source']}"

    lang_text = ""
    if "mt_lang" in field_names and feature["mt_lang"] not in (None, ""):
        lang_text = f", {mountain_lang_label}={feature['mt_lang']}"

    return (
        f"[{mountain_prefix}] {mountain_name}{dist_text}{lang_text}{source_text}\n"
        f"{message}"
    )


def _safe_text(value, fallback="n/a"):
    text = str(value or "").strip()
    return text if text else fallback


def _line_break_html(text):
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_term_display_name(feature, text_lang):
    fields = set(_field_names(feature))
    if text_lang == "en":
        for key in ("term_name", "term_en", "term_id", "term_ko"):
            if key in fields and feature[key] not in (None, ""):
                return str(feature[key])
    for key in ("term_ko", "term_name", "term_id", "term_en"):
        if key in fields and feature[key] not in (None, ""):
            return str(feature[key])
    return "term"


def build_feature_mountain_text(feature, text_lang):
    fields = set(_field_names(feature))
    if "mt_name" not in fields or feature["mt_name"] in (None, ""):
        return ""
    name = str(feature["mt_name"])
    distance_text = ""
    if "mt_dist_m" in fields:
        distance = _safe_float(feature["mt_dist_m"])
        if distance is not None:
            if text_lang == "en":
                distance_text = f", {distance:.0f}m"
            else:
                distance_text = f", 약 {distance:.0f}m"
    return f"{name}{distance_text}"


def build_term_component_text(feature, text_lang):
    name = build_term_display_name(feature, text_lang)
    score = _safe_float(feature["score"]) if "score" in _field_names(feature) else None
    score_text = f"{score:.3f}" if score is not None else "n/a"
    mountain = build_feature_mountain_text(feature, text_lang)
    if mountain:
        if text_lang == "en":
            return f"{name}(score={score_text}, mountain={mountain})"
        return f"{name}(점수={score_text}, 산명={mountain})"
    if text_lang == "en":
        return f"{name}(score={score_text})"
    return f"{name}(점수={score_text})"


def collect_term_cluster(layer, parent_id):
    if parent_id in (None, ""):
        return {}
    try:
        field_names = {field.name() for field in layer.fields()}
    except Exception:
        return {}
    if "term_id" not in field_names or "parent_id" not in field_names:
        return {}

    picked = {}
    for item in layer.getFeatures():
        if item["parent_id"] != parent_id:
            continue
        term_id = str(item["term_id"]).strip()
        if not term_id:
            continue
        current = picked.get(term_id)
        if current is None:
            picked[term_id] = item
            continue
        current_score = _safe_float(current["score"]) if "score" in field_names else None
        next_score = _safe_float(item["score"]) if "score" in field_names else None
        if next_score is None:
            continue
        if current_score is None or next_score > current_score:
            picked[term_id] = item
    return picked


def build_term_cluster_reason(layer, feature, text_lang):
    try:
        field_names = {field.name() for field in layer.fields()}
    except Exception:
        return ""
    if "term_id" not in field_names or "parent_id" not in field_names:
        return ""

    term_id = str(feature["term_id"]).strip() if feature["term_id"] is not None else ""
    parent_id = feature["parent_id"]
    cluster = collect_term_cluster(layer, parent_id)
    if len(cluster) < 2:
        return ""

    def _group(term_ids):
        parts = []
        for key in term_ids:
            node = cluster.get(key)
            if node is not None:
                parts.append(build_term_component_text(node, text_lang))
        return parts

    core = _group(["hyeol", "myeongdang"])
    rear = _group(["jusan", "dunoe", "jojongsan"])
    left = _group(["naecheongnyong", "oecheongnyong"])
    right = _group(["naebaekho", "oebaekho"])
    front = _group(["ansan", "josan", "misa"])
    water = _group(["naesugu", "oesugu", "ipsu"])
    missing_count = max(0, 14 - len(cluster))

    if text_lang == "en":
        lines = [
            "Morphology hierarchy (same parent cluster)",
            f"- core: {', '.join(core) if core else 'insufficient'}",
            f"- rear spine: {', '.join(rear) if rear else 'insufficient'}",
            f"- left support (cheongnyong): {', '.join(left) if left else 'insufficient'}",
            f"- right support (baekho): {', '.join(right) if right else 'insufficient'}",
            f"- frontal guard: {', '.join(front) if front else 'insufficient'}",
            f"- water gates/flow: {', '.join(water) if water else 'insufficient'}",
            f"- missing components: {missing_count}",
        ]
        if term_id == "hyeol":
            lines.append(
                "- hyeol is explained from the full hierarchy above; "
                "support terms can be sparse if local topography is weak."
            )
        return "\n".join(lines)

    lines = [
        "형국 계층 요약(같은 parent 묶음)",
        f"- 핵심(혈/명당): {', '.join(core) if core else '정보 부족'}",
        f"- 배후 축선(주산/둔뇌/조종산): {', '.join(rear) if rear else '정보 부족'}",
        f"- 좌청룡 계열: {', '.join(left) if left else '정보 부족'}",
        f"- 우백호 계열: {', '.join(right) if right else '정보 부족'}",
        f"- 전면 방어(안산/조산/미사): {', '.join(front) if front else '정보 부족'}",
        f"- 수구/입수 계열: {', '.join(water) if water else '정보 부족'}",
        f"- 미검출 항목 수: {missing_count}",
    ]
    if term_id == "hyeol":
        lines.append(
            "- 혈은 상위/하위 형국을 종합해서 판정하므로, "
            "내청룡·외백호 같은 단일 항목보다 설명이 길게 제공됩니다."
        )
    return "\n".join(lines)


def build_feature_reason_overview(feature, text_lang):
    field_names = set(_field_names(feature))
    items = []

    def add_item(text):
        clean = str(text or "").strip()
        if clean:
            items.append(clean)

    def top_scored_components(candidates, limit=3):
        picked = []
        for label_ko, label_en, value in candidates:
            score = _safe_float(value)
            if score is None:
                continue
            label = label_en if text_lang == "en" else label_ko
            picked.append((score, f"{label}: {score:.3f}"))
        picked.sort(key=lambda item: item[0], reverse=True)
        return [text for _score, text in picked[:limit]]

    if "fs_score" in field_names:
        fs_score = _safe_float(feature["fs_score"])
        if fs_score is not None:
            add_item(
                f"{'Overall suitability' if text_lang == 'en' else '종합 적합도'}: {fs_score:.3f}"
            )
        items.extend(
            top_scored_components(
                [
                    ("지형 균형", "Terrain balance", feature["fs_form"] if "fs_form" in field_names else None),
                    ("배후 연속성", "Rear continuity", feature["fs_long"] if "fs_long" in field_names else None),
                    ("수계 적합", "Hydro fit", feature["fs_water"] if "fs_water" in field_names else None),
                    ("DEM 수계 적합", "DEM hydro fit", feature["fs_demwtr"] if "fs_demwtr" in field_names else None),
                    ("사신사", "Four-support form", feature["fs_sashinsa"] if "fs_sashinsa" in field_names else None),
                    ("포위감", "Enclosure", feature["fs_enclosure"] if "fs_enclosure" in field_names else None),
                ],
                limit=3 if fs_score is None else 2,
            )
        )
        if "fs_water_m" in field_names:
            water_m = _safe_float(feature["fs_water_m"])
            if water_m is not None:
                add_item(
                    f"{'Water distance' if text_lang == 'en' else '수계 거리'}: {water_m:.1f}m"
                )
        return items[:3]

    if "term_id" in field_names:
        add_item(
            f"{'Term' if text_lang == 'en' else '용어'}: {build_term_display_name(feature, text_lang)}"
        )
        score = _safe_float(feature["score"]) if "score" in field_names else None
        if score is not None:
            add_item(f"{'Score' if text_lang == 'en' else '점수'}: {score:.3f}")
        fit_score = _safe_float(feature["fit_sc"]) if "fit_sc" in field_names else None
        if fit_score is not None:
            add_item(f"{'Fit' if text_lang == 'en' else '적합도'}: {fit_score:.3f}")
        radius_m = _safe_float(feature["radius_m"]) if "radius_m" in field_names else None
        if radius_m is not None:
            add_item(f"{'Radius' if text_lang == 'en' else '반경'}: {radius_m:.1f}m")
        return items[:3]

    if {"src_id", "dst_id"} <= field_names:
        src = _safe_text(feature["src_en"] if text_lang == "en" and "src_en" in field_names else feature["src_ko"] if "src_ko" in field_names else feature["src_id"])
        dst = _safe_text(feature["dst_en"] if text_lang == "en" and "dst_en" in field_names else feature["dst_ko"] if "dst_ko" in field_names else feature["dst_id"])
        add_item(f"{'Path' if text_lang == 'en' else '연결'}: {src} -> {dst}")
        score = _safe_float(feature["score"]) if "score" in field_names else None
        if score is not None:
            add_item(f"{'Score' if text_lang == 'en' else '점수'}: {score:.3f}")
        length_m = _safe_float(feature["len_m"]) if "len_m" in field_names else None
        if length_m is not None:
            add_item(f"{'Length' if text_lang == 'en' else '길이'}: {length_m:.1f}m")
        return items[:3]

    if "ridge_class" in field_names:
        ridge_name = feature["ridge_en"] if text_lang == "en" and "ridge_en" in field_names else feature["ridge_ko"] if "ridge_ko" in field_names else feature["ridge_class"]
        add_item(f"{'Ridge class' if text_lang == 'en' else '산줄기 분류'}: {_safe_text(ridge_name)}")
        ridge_score = _safe_float(feature["ridge_score"]) if "ridge_score" in field_names else None
        if ridge_score is not None:
            add_item(f"{'Ridge score' if text_lang == 'en' else '산줄기 점수'}: {ridge_score:.3f}")
        strength = _safe_float(feature["strength"]) if "strength" in field_names else None
        if strength is not None:
            add_item(f"{'Strength' if text_lang == 'en' else '강도'}: {strength:.3f}")
        return items[:3]

    if "stream_class" in field_names:
        add_item(f"{'Hydro class' if text_lang == 'en' else '수계 분류'}: {_safe_text(feature['stream_class'])}")
        order = _safe_float(feature["order"]) if "order" in field_names else None
        if order is not None:
            add_item(f"{'Order' if text_lang == 'en' else '차수'}: {order:.0f}")
        length_m = _safe_float(feature["len"]) if "len" in field_names else None
        if length_m is not None:
            add_item(f"{'Length' if text_lang == 'en' else '길이'}: {length_m:.1f}m")
        return items[:3]

    return items[:3]


def build_feature_reason_limitations(feature, text_lang):
    field_names = set(_field_names(feature))
    if "fs_score" in field_names:
        if text_lang == "en":
            return [
                "This score is not a probability and does not prove the presence of an archaeological feature.",
                "The result can change with DEM quality, hydro input, and candidate-point coverage.",
                "Use this with field survey, excavation context, and documentary evidence.",
            ]
        return [
            "이 점수는 확률값이 아니며 실제 유적 존재를 입증하지 않습니다.",
            "DEM 품질, 수계 입력, 후보점 분포에 따라 결과가 달라질 수 있습니다.",
            "반드시 현장조사, 발굴 맥락, 문헌 근거와 함께 봐야 합니다.",
        ]

    if {"term_id", "parent_id"} <= field_names:
        if text_lang == "en":
            return [
                "A term point is an interpretive terrain marker, not a standalone site verdict.",
                "Its position can move with DEM resolution and smoothing choices.",
                "A single term is weaker than the full parent cluster or surrounding evidence.",
            ]
        return [
            "용어 포인트는 해석용 지형 표지일 뿐, 단독 입지 판정이 아닙니다.",
            "DEM 해상도와 스무딩 방식에 따라 위치가 조금 달라질 수 있습니다.",
            "개별 용어 하나보다 parent 묶음 전체와 주변 근거를 함께 봐야 합니다.",
        ]

    if {"src_id", "dst_id"} <= field_names:
        if text_lang == "en":
            return [
                "A link line shows interpreted structure, not a real path or route.",
                "The curve depends on smoothing and link-plan rules.",
                "Use it as a relational cue between terms, not as proof on its own.",
            ]
        return [
            "연결선은 해석된 구조를 보여줄 뿐, 실제 길이나 이동 경로를 뜻하지 않습니다.",
            "곡선 형태는 스무딩과 링크 규칙에 영향을 받습니다.",
            "단독 증거가 아니라 용어 사이 관계를 읽는 보조선으로 봐야 합니다.",
        ]

    if text_lang == "en":
        return [
            "This layer supports terrain reading and should not be treated as proof by itself.",
            "Results depend on DEM quality, CRS choice, and hydro input.",
            "Always interpret with surrounding evidence and domain context.",
        ]
    return [
        "이 레이어는 지형 읽기를 돕는 보조 결과이며 단독 입증 자료가 아닙니다.",
        "DEM 품질, 좌표계, 수계 입력에 따라 결과가 달라질 수 있습니다.",
        "반드시 주변 근거와 맥락을 함께 놓고 해석해야 합니다.",
    ]


def build_reason_popup_html(
    title,
    *,
    overview_title,
    overview_items,
    detail_title,
    message,
    cluster_title=None,
    cluster_reason=None,
    limitations_title,
    limitations_items,
):
    safe_title = escape(str(title or ""))
    overview_html = "".join(
        f"<li>{escape(str(item))}</li>" for item in (overview_items or []) if str(item).strip()
    ) or "<li>-</li>"
    limitations_html = "".join(
        f"<li>{escape(str(item))}</li>" for item in (limitations_items or []) if str(item).strip()
    ) or "<li>-</li>"
    cluster_html = ""
    if str(cluster_reason or "").strip():
        cluster_html = (
            f"<h4>{escape(str(cluster_title or 'Cluster'))}</h4>"
            f"<p>{_line_break_html(cluster_reason)}</p>"
        )
    return (
        f"<h3>{safe_title}</h3>"
        f"<h4>{escape(str(overview_title or 'Overview'))}</h4>"
        f"<ul>{overview_html}</ul>"
        f"<h4>{escape(str(detail_title or 'Details'))}</h4>"
        f"<p>{_line_break_html(message)}</p>"
        f"{cluster_html}"
        f"<h4>{escape(str(limitations_title or 'Limitations'))}</h4>"
        f"<ul>{limitations_html}</ul>"
    )
