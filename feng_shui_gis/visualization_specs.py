# -*- coding: utf-8 -*-
"""Pure visual-language specs for Feng Shui layer rendering."""

from __future__ import annotations


def _clamp(value, low, high):
    return max(low, min(high, value))


def _hex_rgb(value):
    text = str(value or "").strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return (127, 127, 127)
    try:
        return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return (127, 127, 127)


def mix_hex(source, target, ratio):
    ratio_value = _clamp(float(ratio), 0.0, 1.0)
    src = _hex_rgb(source)
    dst = _hex_rgb(target)
    blended = tuple(
        int(round((src[index] * (1.0 - ratio_value)) + (dst[index] * ratio_value)))
        for index in range(3)
    )
    return "#{:02x}{:02x}{:02x}".format(*blended)


def rgba_from_hex(color, alpha):
    red, green, blue = _hex_rgb(color)
    alpha_value = int(round(_clamp(float(alpha), 0.0, 1.0) * 255.0))
    return f"{red},{green},{blue},{alpha_value}"


def ribbon_line_layers(
    base_color,
    base_width,
    *,
    outer_scale=1.7,
    body_scale=1.0,
    core_scale=0.38,
    outer_alpha=0.18,
    body_alpha=0.70,
    core_alpha=0.92,
    outer_mix="#101010",
    outer_mix_ratio=0.38,
    core_mix="#f7f3e8",
    core_mix_ratio=0.22,
):
    width = max(0.15, float(base_width))
    shadow_color = mix_hex(base_color, outer_mix, outer_mix_ratio)
    core_color = mix_hex(base_color, core_mix, core_mix_ratio)
    return [
        {
            "color": rgba_from_hex(shadow_color, outer_alpha),
            "width": max(0.35, width * outer_scale),
        },
        {
            "color": rgba_from_hex(base_color, body_alpha),
            "width": max(0.20, width * body_scale),
        },
        {
            "color": rgba_from_hex(core_color, core_alpha),
            "width": max(0.12, width * core_scale),
        },
    ]


def orb_marker_layers(
    fill_color,
    size,
    stroke_color,
    stroke_width,
    *,
    outer_scale=1.8,
    body_scale=1.0,
    core_scale=0.42,
    outer_alpha=0.16,
    body_alpha=0.78,
    core_alpha=0.95,
):
    base_size = max(1.0, float(size))
    outline = max(0.10, float(stroke_width))
    return [
        {
            "name": "circle",
            "color": rgba_from_hex(mix_hex(fill_color, "#ffffff", 0.08), outer_alpha),
            "size": max(2.4, base_size * outer_scale),
            "outline_color": "0,0,0,0",
            "outline_width": 0.0,
        },
        {
            "name": "circle",
            "color": rgba_from_hex(fill_color, body_alpha),
            "size": max(1.4, base_size * body_scale),
            "outline_color": rgba_from_hex(stroke_color, 0.72),
            "outline_width": max(0.20, outline * 0.95),
        },
        {
            "name": "circle",
            "color": rgba_from_hex(mix_hex(fill_color, "#fff1c4", 0.48), core_alpha),
            "size": max(0.9, base_size * core_scale),
            "outline_color": rgba_from_hex(stroke_color, 0.24),
            "outline_width": max(0.10, outline * 0.24),
        },
    ]


def ridge_symbol_profiles():
    return {
        "major": {
            "legend_color": "#55645a",
            "legend_width": 2.3,
            "legend_opacity": 0.78,
            "layers": ribbon_line_layers(
                "#55645a",
                2.35,
                outer_scale=1.8,
                body_scale=1.0,
                core_scale=0.34,
                outer_alpha=0.22,
                body_alpha=0.82,
                core_alpha=0.96,
                outer_mix="#15110d",
                outer_mix_ratio=0.48,
                core_mix="#eef0df",
                core_mix_ratio=0.38,
            ),
        },
        "minor": {
            "legend_color": "#74847d",
            "legend_width": 1.15,
            "legend_opacity": 0.46,
            "layers": ribbon_line_layers(
                "#74847d",
                1.15,
                outer_scale=1.65,
                body_scale=0.92,
                core_scale=0.30,
                outer_alpha=0.14,
                body_alpha=0.44,
                core_alpha=0.70,
                outer_mix="#171717",
                outer_mix_ratio=0.32,
                core_mix="#edf2e8",
                core_mix_ratio=0.22,
            ),
        },
    }


def hydro_symbol_profiles():
    classes = {
        "main": ("#0f4c81", 2.25),
        "secondary": ("#1d67ad", 1.75),
        "branch": ("#2e87d0", 1.25),
        "minor": ("#66b4ec", 0.92),
    }
    profiles = {}
    for class_id, (base_color, width) in classes.items():
        profiles[class_id] = {
            "legend_color": base_color,
            "legend_width": width,
            "layers": ribbon_line_layers(
                base_color,
                width,
                outer_scale=1.75,
                body_scale=1.0,
                core_scale=0.40,
                outer_alpha=0.18 if class_id != "minor" else 0.12,
                body_alpha=0.68 if class_id != "minor" else 0.42,
                core_alpha=0.93 if class_id != "minor" else 0.74,
                outer_mix="#03111f",
                outer_mix_ratio=0.42,
                core_mix="#f3fbff",
                core_mix_ratio=0.35,
            ),
        }
    return profiles


def term_link_symbol_layers(term_id, base_style):
    color, width = base_style
    emphasis = 1.18 if str(term_id) in ("myeongdang", "ipsu") else 1.0
    return ribbon_line_layers(
        color,
        max(0.45, float(width) * emphasis),
        outer_scale=1.55,
        body_scale=0.96,
        core_scale=0.34,
        outer_alpha=0.12,
        body_alpha=0.34,
        core_alpha=0.82,
        outer_mix="#161616",
        outer_mix_ratio=0.28,
        core_mix="#fff7df",
        core_mix_ratio=0.18,
    )


def term_point_symbol_layers(term_id, base_style):
    fill_color, size, stroke_color, stroke_width = base_style
    emphasis = str(term_id or "")
    if emphasis == "hyeol":
        return orb_marker_layers(
            fill_color,
            max(4.8, float(size) * 1.16),
            stroke_color,
            stroke_width,
            outer_scale=2.55,
            body_scale=1.18,
            core_scale=0.48,
            outer_alpha=0.22,
            body_alpha=0.86,
            core_alpha=0.98,
        )
    if emphasis == "myeongdang":
        return orb_marker_layers(
            fill_color,
            max(4.0, float(size) * 1.05),
            stroke_color,
            stroke_width,
            outer_scale=2.18,
            body_scale=1.10,
            core_scale=0.46,
            outer_alpha=0.18,
            body_alpha=0.80,
            core_alpha=0.96,
        )
    return orb_marker_layers(
        fill_color,
        max(3.0, float(size) * 0.92),
        stroke_color,
        stroke_width,
        outer_scale=1.72,
        body_scale=0.96,
        core_scale=0.40,
        outer_alpha=0.12,
        body_alpha=0.70,
        core_alpha=0.92,
    )


def hyeol_field_symbol_layers(base_color="#c86a52"):
    edge_color = mix_hex(base_color, "#41211a", 0.46)
    glow_color = mix_hex(base_color, "#fff3dd", 0.58)
    return [
        {
            "color": rgba_from_hex(glow_color, 0.08),
            "outline_color": rgba_from_hex(edge_color, 0.18),
            "outline_width": 1.6,
        },
        {
            "color": rgba_from_hex(base_color, 0.20),
            "outline_color": rgba_from_hex(edge_color, 0.44),
            "outline_width": 0.9,
        },
        {
            "color": rgba_from_hex(mix_hex(base_color, "#ffd7b5", 0.36), 0.06),
            "outline_color": rgba_from_hex(glow_color, 0.56),
            "outline_width": 0.32,
        },
    ]


def support_field_symbol_layers(term_id):
    emphasis = str(term_id or "")
    if emphasis == "sashinsa":
        base_color = "#5d8b63"
        edge_color = mix_hex(base_color, "#18301d", 0.50)
        glow_color = mix_hex(base_color, "#eef7e6", 0.60)
        return [
            {
                "color": rgba_from_hex(glow_color, 0.06),
                "outline_color": rgba_from_hex(edge_color, 0.12),
                "outline_width": 1.8,
            },
            {
                "color": rgba_from_hex(base_color, 0.13),
                "outline_color": rgba_from_hex(edge_color, 0.28),
                "outline_width": 0.85,
            },
            {
                "color": rgba_from_hex(mix_hex(base_color, "#d9ead1", 0.34), 0.04),
                "outline_color": rgba_from_hex(glow_color, 0.42),
                "outline_width": 0.26,
            },
        ]

    base_color = "#b9844d"
    edge_color = mix_hex(base_color, "#3d2414", 0.46)
    glow_color = mix_hex(base_color, "#fff0db", 0.54)
    return [
        {
            "color": rgba_from_hex(glow_color, 0.07),
            "outline_color": rgba_from_hex(edge_color, 0.14),
            "outline_width": 1.4,
        },
        {
            "color": rgba_from_hex(base_color, 0.15),
            "outline_color": rgba_from_hex(edge_color, 0.34),
            "outline_width": 0.72,
        },
        {
            "color": rgba_from_hex(mix_hex(base_color, "#ffdcb2", 0.34), 0.05),
            "outline_color": rgba_from_hex(glow_color, 0.50),
            "outline_width": 0.24,
        },
    ]
