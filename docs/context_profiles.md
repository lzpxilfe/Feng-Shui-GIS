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

See:
- `docs/reference_audit.md`
- `docs/research_matrix.md`
- `docs/regional_period_notes.md`

## Research-Grade Workflow Recommendation

1. Freeze version + config snapshot.
2. Calibrate parameters with local archaeological truth data.
3. Report metrics (AUC/PR/F1) and uncertainty.
4. Publish calibration delta from default config.
