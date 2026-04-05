# Context Profiles (Config-Driven)

Files:
- `feng_shui_gis/config/contexts.json`
- `feng_shui_gis/config/profiles.json`
- `feng_shui_gis/config/terms.json`
- `feng_shui_gis/config/analysis_rules.json`

## Important

These config profiles are transparent and editable, but they are not all equally evidence-backed.

They are also not the first interpretive layer anymore. The plugin should explain
`principle evidence` from terrain first, then show context/profile adjustments as
secondary overlays.

- DEM/ridge/hydro extraction parameters: reproducible algorithm settings.
- Country/period bias fields: initial research priors.
- Profile-level paper evidence (`profiles.json`: `paper_evidence`): additive profile overrides with citation metadata.
- Principle-first mapping and current terrain-to-principle translation:
  `docs/PRINCIPLES.md`

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

The context catalogs now include a simple visibility tier policy:

- `stable`: profile is supported by broader comparative evidence or multiple source
  families and is shown by default in the UI.
- `experimental`: profile is useful but limited (small sample, contested mapping
  boundaries, or strong local scope), hidden unless the user enables
  "Preset / Context Scope → Show exploratory presets and region profiles".

Current examples:

- `ryukyu` and `southeast_asia` are marked `experimental` because the source
  layer is still sparse and boundary definitions are under active discussion.
- `global_apm` is now `experimental` because the cross-region baseline is useful
  for comparison but too broad to present as a default context.
- `korea`, `china`, `japan`, and `east_asia` remain `stable` defaults.

The same conservative rule now applies to `profiles.json` as well:

- `general`, `tomb`, `house`, `village`, `tomb_kr`, and `village_kr` are shown
  by default.
- `well`, `temple`, `urban_real_estate`, and `global_apm` are hidden unless the
  user enables exploratory presets.

This policy is meant to reduce accidental overfitting to very specific
sub-regions while keeping them available for focused studies and future
validation.
