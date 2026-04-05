#!/usr/bin/env python3
"""Copy user-provided DEM and vector inputs into a fixture case folder."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED_SHAPEFILE_SUFFIXES = [".shp", ".shx", ".dbf", ".prj"]
OPTIONAL_SHAPEFILE_SUFFIXES = [".cpg"]


def _ensure_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} 파일을 찾지 못했습니다: {path}")


def _copy_with_sidecar(src: Path, dst: Path) -> None:
    src = src.resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src != dst.resolve():
        shutil.copy2(src, dst)

    if src.suffix.lower() != ".shp":
        return

    base = src.with_suffix("")
    dst_base = dst.with_suffix("")
    for suffix in REQUIRED_SHAPEFILE_SUFFIXES + OPTIONAL_SHAPEFILE_SUFFIXES:
        side_src = base.with_suffix(suffix)
        side_dst = dst_base.with_suffix(suffix)
        if side_src.exists() and side_src.resolve() != side_dst.resolve():
            shutil.copy2(side_src, dst_base.with_suffix(suffix))


def _load_case_inputs(case_dir: Path) -> dict:
    case_json = case_dir / "case.json"
    if not case_json.exists():
        raise FileNotFoundError(f"case.json이 없습니다: {case_json}")
    payload = json.loads(case_json.read_text(encoding="utf-8"))
    inputs = payload.get("inputs", {})
    if not isinstance(inputs, dict) or not inputs:
        raise RuntimeError(f"case.json에 inputs 항목이 없습니다: {case_json}")
    return inputs


def _copy_inputs(case_dir: Path, demo_inputs: dict[str, Path]) -> dict[str, str]:
    case_inputs = _load_case_inputs(case_dir)
    results = {}

    for key, relative_path in case_inputs.items():
        if key not in demo_inputs:
            continue

        src = demo_inputs[key]
        dst = (case_dir / relative_path).resolve()
        _ensure_file(src, key)
        _copy_with_sidecar(src, dst)
        results[key] = str(dst)

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_dir", type=Path, help="fixtures/<case_id> 또는 테스트 케이스 경로")
    parser.add_argument("--dem", required=True, type=Path, help="DEM GeoTIFF 경로")
    parser.add_argument("--sites", required=True, type=Path, help="sites 포인트 샤프 경로")
    parser.add_argument("--water", required=True, type=Path, help="water 포인트/폴리라인 샤프 경로")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    case_dir = (ROOT / args.case_dir).resolve() if not args.case_dir.is_absolute() else args.case_dir.resolve()
    if not case_dir.exists():
        raise FileNotFoundError(f"케이스 경로가 없습니다: {case_dir}")

    copied = _copy_inputs(
        case_dir=case_dir,
        demo_inputs={"dem": args.dem, "sites": args.sites, "water": args.water},
    )

    print(f"✅ {case_dir.name} 입력 파일 반영 완료")
    for key, path in copied.items():
        print(f"  - {key}: {path}")


if __name__ == "__main__":
    main()
