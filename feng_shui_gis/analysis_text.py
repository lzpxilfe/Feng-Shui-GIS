# -*- coding: utf-8 -*-
"""Pure formatting and label helpers shared by analysis modules."""

from __future__ import annotations


def fmt_num(value, digits=3):
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def azimuth_label(azimuth):
    if azimuth is None:
        return "ring"
    directions = [
        "북",
        "북동",
        "동",
        "남동",
        "남",
        "남서",
        "서",
        "북서",
    ]
    idx = int(((azimuth % 360.0) + 22.5) // 45.0) % 8
    return directions[idx]


def score_band_label(value):
    if value is None:
        return "정보 없음"
    if value >= 0.8:
        return "매우 양호"
    if value >= 0.65:
        return "양호"
    if value >= 0.5:
        return "보통"
    return "낮음"


def tpi_hint(tpi_norm):
    if tpi_norm is None:
        return "지형 곡률 정보 없음"
    if tpi_norm <= -0.08:
        return "완만한 오목 지형에 가까움"
    if tpi_norm < 0.08:
        return "평탄에 가까운 중립 지형"
    return "완만한 볼록 지형에 가까움"


def tpi_class_label(tpi_small, tpi_large=None):
    if tpi_small is None:
        return "지형정보 없음"
    if tpi_large is None:
        if tpi_small > 0.10:
            return "능선(능)"
        if tpi_small < -0.10:
            return "계곡(곡)"
        return "중간 사면"
    if tpi_large > 0.10:
        if tpi_small > 0.10:
            return "산릉(山陵)"
        if tpi_small < -0.10:
            return "산지 계곡"
        return "중산복(中山腹)"
    if tpi_large < -0.10:
        if tpi_small > 0.10:
            return "평야 구릉"
        if tpi_small < -0.10:
            return "평지 저습지"
        return "평원 사면"
    if tpi_small > 0.10:
        return "대지 능선"
    if tpi_small < -0.10:
        return "대지 계곡"
    return "평탄지(平)"


def sashinsa_hint(sashinsa_score):
    if sashinsa_score is None:
        return "사신사 정보 없음"
    if sashinsa_score >= 0.75:
        return "사신사 배치 우수"
    if sashinsa_score >= 0.55:
        return "사신사 배치 양호"
    if sashinsa_score >= 0.35:
        return "사신사 배치 보통"
    return "사신사 배치 미흡"


def enclosure_hint(enclosure_index):
    if enclosure_index is None:
        return "장풍 정보 없음"
    if enclosure_index >= 0.75:
        return "장풍득수 조건 우수"
    if enclosure_index >= 0.55:
        return "장풍 양호"
    if enclosure_index >= 0.35:
        return "장풍 보통"
    return "장풍 미흡(개방지형)"
