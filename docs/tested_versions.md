# Tested Versions & Known Limitations

Updated: 2026-04-01

이 문서는 “현재 저장소가 무엇을 기준으로 공개되고 있는지”를 짧게 보여주기 위한 공개용 기준선입니다.

## Tested baseline

- Plugin metadata minimum QGIS version: `3.28`
- Repository automation currently runs on: `ubuntu-latest`
- Repository automation currently uses: `Python 3.11`
- Release guard / asset smoke are maintained against this baseline

## Tested OS status

- Automated repository checks: `Linux (ubuntu-latest)`
- `macOS`와 `Windows`는 저장소 자동화 기준선이 아직 별도로 문서화되어 있지 않습니다.
- 따라서 다른 OS에서 문제를 재현할 때는 support bundle과 환경 정보가 특히 중요합니다.

## Recommended environment assumptions

- projected CRS in meters strongly recommended
- DEM quality strongly affects ridge / hydro / distance-based interpretation
- curated water layers are preferred over auto-hydro when available

## Known limitations

- This plugin is a **heuristic terrain interpretation tool**
- It is **not a predictive truth model**
- `fs_score` should not be read as site-presence probability
- local calibration is **not standalone validation**
- compare output means **gain/drop relative to the selected profile**
- auto-hydro is a fallback for first-pass reading, not a replacement for trusted hydrology
- no-water / no-candidate / bad-CRS paths can still produce exploratory or incomplete outputs

## Before reporting an issue

1. Export a `Support Bundle`
2. Record QGIS version, plugin version, and operating system
3. Note whether the run used auto-hydro, advanced context, or local calibration
