# Principle-First Interpretation

This plugin should be read as a `principle-first` terrain interpreter, not as a paper-lookup engine.

## Core Claim

The primary claim is not:

- "this place is a tomb"
- "this profile says Korea/China/Japan"

The primary claim is:

- how strongly the terrain satisfies explicit Feng Shui principles such as `배산/형국`, `혈 조건`, `사신사`, `장풍/감쌈`, and `득수/수계 관계`

## Layer Order

Interpretation should be stacked in this order:

1. `Principle evidence`
2. `Measured terrain indicators`
3. `Regional / period calibration overlays`
4. `Reference and paper validation`

This keeps the plugin honest about what it is directly measuring versus what it is borrowing from literature.

## Current Principle Mapping

The current site-scoring layer translates existing indicators into five principle buckets:

- `배산/형국`: current `form_score`
- `혈 조건`: current `long_score` + scored `tpi`
- `사신사`: current `sashinsa_score`
- `장풍/감쌈`: current `enclosure_index`
- `득수/수계 관계`: combined hydro score + DEM wetness + water distance

This is deliberately conservative. It does not claim to reconstruct the whole classical ontology yet; it exposes the parts already measured by the code.

## Role of Profiles and Context

`profiles.json` and `contexts.json` should be treated as secondary calibration layers.

- They can bias weights and target values.
- They can help compare regional or historical variants.
- They should not be the plugin's first explanation for why a place scored the way it did.

## Role of References

References are for validation and provenance:

- to show where a bias or target came from
- to justify later calibration choices
- to document uncertainty and evidence quality

References should not substitute for explicit spatial rules.
