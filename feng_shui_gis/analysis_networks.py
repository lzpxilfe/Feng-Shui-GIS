# -*- coding: utf-8 -*-
"""Pure helpers for stream ordering and path tracing."""

from __future__ import annotations

from collections import defaultdict, deque


def compute_stream_order(nodes, downstream, upstream):
    pending = {key: len(upstream.get(key, [])) for key in nodes.keys()}
    seeds = [key for key, count in pending.items() if count == 0]
    seeds.sort(key=lambda key: nodes[key]["elev"], reverse=True)
    queue = deque(seeds)
    order = {}
    collected = defaultdict(list)

    while queue:
        key = queue.popleft()
        incoming = collected.get(key, [])
        if not incoming:
            order[key] = 1
        else:
            max_value = max(incoming)
            if incoming.count(max_value) >= 2:
                order[key] = max_value + 1
            else:
                order[key] = max_value

        target = downstream.get(key)
        if target is None:
            continue
        collected[target].append(order[key])
        pending[target] -= 1
        if pending[target] == 0:
            queue.append(target)

    return order


def trace_downstream_path(start, selected_downstream, upstream_selected, visited_edges):
    if start not in selected_downstream:
        return None

    path = [start]
    current = start
    while current in selected_downstream:
        target = selected_downstream[current]
        edge_key = (current, target)
        if edge_key in visited_edges:
            break
        visited_edges.add(edge_key)
        path.append(target)
        if upstream_selected.get(target, 0) != 1:
            break
        current = target

    if len(path) < 2:
        return None
    return path


def stream_class(order):
    if order >= 6:
        return "main"
    if order >= 5:
        return "secondary"
    if order >= 4:
        return "branch"
    return "minor"
