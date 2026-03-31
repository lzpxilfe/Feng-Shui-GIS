# Context Profiles (Config-Driven)

Files:
- `feng_shui_gis/config/contexts.json`
- `feng_shui_gis/config/profiles.json`
- `feng_shui_gis/config/terms.json`
- `feng_shui_gis/config/analysis_rules.json`

## Important

These config profiles are transparent and editable, but they are not all equally evidence-backed.

- DEM/ridge/hydro extraction parameters: reproducible algorithm settings.
- Country/period bias fields: initial research priors.
- Profile-level paper evidence (`profiles.json`: `paper_evidence`): additive profile overrides with citation metadata.

See:
- `docs/reference_audit.md`
- `docs/research_matrix.md`
- `docs/regional_period_notes.md`

## Research-Grade Workflow Recommendation

1. Freeze version + config snapshot.
2. Calibrate parameters with local archaeological truth data.
3. Report metrics (AUC/PR/F1) and uncertainty.
4. Publish calibration delta from default config.

### Profile Evidence Integration Pattern

For each `profiles.json` model, you can keep incremental `paper_evidence` blocks.

- `weight_bias`: profile-specific additive bias on indicator weights.
- `term_bias`: extra term-level prioritization used during term extraction.
- `target_overrides` (or top-level `slope_target`/`slope_sigma`/`tpi_target`/`tpi_sigma`): numeric override for direct model targets.
- Citation source strings should resolve through `feng_shui_gis/config/references.json`; they may be DOI values or catalog `id` values for classical texts and editions without DOI.

Each entry can carry `source_doi`, `evidence_level`, and `note` so the plugin can
carry provenance into feature reason strings and calibration reports.

## Paper Evidence Update Flow (Operational)

1. Add or revise a paper block in `feng_shui_gis/config/profiles.json`.
2. Ensure every citation string is already listed in `feng_shui_gis/config/references.json`.
3. Re-run calibration to regenerate report outputs after context/profile changes.
4. Check the calibration report for:
   - `Paper Evidence` summary
   - `Paper references`

This makes plugin improvements auditable and repeatable as new references for
Asian historical landscape reading are added.

## Baseline Recommendation

Use the neutral/general context as the first comparison frame when the research
question is about broad spatial-geographic perception rather than a narrowly
defined national or period tradition. Add country/period splits only when they
improve held-out performance or are directly justified by the source material.

## Region Profile Stability Policy

- `stable`: profile is applied by default in the UI.
- `experimental`: shown when "Show exploratory region profiles" is enabled.

Current assignment:

- `ryukyu` and `southeast_asia` are `experimental`:
  - direct citation coverage is concentrated in limited case studies,
  - boundaries and historical comparability are under active discussion.
- `east_asia`, `korea`, `china`, `japan`, and `global_apm` remain `stable`.

This keeps default analyses centered on broadly comparable profiles, while still
making narrower regional priors available for explicitly exploratory workflows.
